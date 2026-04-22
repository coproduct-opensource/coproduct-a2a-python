"""Tests for LangGraph + CrewAI adapters.

Uses a fake Client that records calls — the adapters don't touch
the network in these tests. Real end-to-end coverage lives in the
oracle which runs against a live server; here we only pin the
state-shaping contract.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from coproduct_a2a.constants import EXTENSION_URI
from coproduct_a2a.crewai import wrap_agent_with_provenance
from coproduct_a2a.langgraph import ProvableCoordinationNode


class _FakeClient:
    def __init__(self, response: Dict[str, Any]) -> None:
        self.response = response
        self.calls: List[Dict[str, Any]] = []

    def send_message(self, message: str, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append({"message": message, "kwargs": kwargs})
        return self.response


def _sample_response() -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": "c1",
        "result": {"id": "task-1", "state": "submitted"},
        "extensions": {
            EXTENSION_URI: {
                "manifest_version": "1",
                "provenance_trail": [],
                "capability_envelope_sha": "",
                "cohort_witnesses": [],
                "hydrate_log_rev": 5,
                "signature": "ed25519:AAAA",
            }
        },
    }


def test_langgraph_node_attaches_manifest():
    client = _FakeClient(_sample_response())
    node = ProvableCoordinationNode(client)  # type: ignore[arg-type]
    out = node({"message": "hi"})
    assert out["a2a_task"]["id"] == "task-1"
    assert out["provenance_manifest"]["hydrate_log_rev"] == 5


def test_langgraph_node_rejects_empty_message():
    node = ProvableCoordinationNode(_FakeClient(_sample_response()))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        node({"message": ""})


def test_langgraph_node_preserves_other_state_keys():
    node = ProvableCoordinationNode(_FakeClient(_sample_response()))  # type: ignore[arg-type]
    out = node({"message": "hi", "user": "alice", "count": 3})
    assert out["user"] == "alice"
    assert out["count"] == 3


def test_langgraph_node_manifest_absent_when_no_extension():
    bare_response = {
        "jsonrpc": "2.0",
        "id": "c1",
        "result": {"id": "t2", "state": "submitted"},
    }
    node = ProvableCoordinationNode(_FakeClient(bare_response))  # type: ignore[arg-type]
    out = node({"message": "hi"})
    assert out["provenance_manifest"] is None


def test_crewai_wrapper_threads_manifest():
    class _Agent:
        role = "Reporter"

        def execute_task(self, task: Any) -> str:
            return f"did-{task}"

    inner = _Agent()
    client = _FakeClient(_sample_response())
    wrapped = wrap_agent_with_provenance(inner, client)  # type: ignore[arg-type]

    # Forwards attribute access to inner.
    assert wrapped.role == "Reporter"

    # send_message routes through A2A + captures the manifest.
    response = wrapped.send_message("hi")
    assert response["result"]["id"] == "task-1"
    assert wrapped.last_manifest["hydrate_log_rev"] == 5

    # execute_task delegates to the wrapped agent.
    assert wrapped.execute_task("x") == "did-x"
