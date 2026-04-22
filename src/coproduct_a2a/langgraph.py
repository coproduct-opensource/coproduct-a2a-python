"""LangGraph adapter — wrap a LangGraph node with Coproduct A2A.

Usage::

    from langgraph.graph import StateGraph
    from coproduct_a2a import Client
    from coproduct_a2a.langgraph import ProvableCoordinationNode

    client = Client.from_env()
    graph = StateGraph(AgentState)
    graph.add_node("agent", ProvableCoordinationNode(client))

This module deliberately does NOT import langgraph — it's a thin
shim that produces a node-callable suitable for langgraph without
requiring langgraph installed at SDK-import time. Users who add
`langgraph` as a dep in their project get a working integration;
users who don't can still import `Client` without drag.
"""

from __future__ import annotations

from typing import Any, Mapping

from coproduct_a2a.client import Client
from coproduct_a2a.constants import EXTENSION_URI


class ProvableCoordinationNode:
    """A LangGraph-compatible node that forwards state to
    `message/send` and attaches the verified provenance manifest to
    the outgoing state as ``state["provenance_manifest"]``.

    Expected state shape (keys beyond these are forwarded unchanged):

        {"message": "<text to send>", ...}

    Output state adds:

        {"a2a_task": <Task dict>,
         "provenance_manifest": <Manifest dict>}

    When the response has no manifest (e.g. server ran with
    ``signing_keypair = None``), ``provenance_manifest`` is set to
    ``None`` — downstream nodes can decide whether to fail closed.
    """

    def __init__(self, client: Client) -> None:
        self.client = client

    def __call__(self, state: Mapping[str, Any]) -> dict:
        message = state.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError(
                "ProvableCoordinationNode requires state['message'] as a non-empty string"
            )
        response = self.client.send_message(
            message, session_id=state.get("session_id")
        )
        out = dict(state)
        out["a2a_task"] = response.get("result")
        ext = response.get("extensions") or {}
        out["provenance_manifest"] = ext.get(EXTENSION_URI)
        return out
