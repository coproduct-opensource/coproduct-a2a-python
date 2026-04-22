"""CrewAI wrapper — attach provable-coordination guarantees to an
agent's tool invocations.

Usage::

    from crewai import Agent
    from coproduct_a2a import Client
    from coproduct_a2a.crewai import wrap_agent_with_provenance

    client = Client.from_env()
    agent = Agent(role="Reporter", goal="Summarize the workspace")
    wrapped = wrap_agent_with_provenance(agent, client)

Like :mod:`coproduct_a2a.langgraph`, this does NOT import crewai at
SDK-load; the wrapping logic treats the agent object as duck-typed.
"""

from __future__ import annotations

from typing import Any

from coproduct_a2a.client import Client
from coproduct_a2a.constants import EXTENSION_URI


def wrap_agent_with_provenance(agent: Any, client: Client) -> Any:
    """Return a proxy around ``agent`` whose action-delivery methods
    route through the Coproduct A2A client, surfacing the verified
    manifest to the wrapping crew's execution log.

    The wrapper attaches two attributes to the returned proxy:

    - ``last_manifest`` — the provable-coordination manifest from
      the most recent call, or ``None`` if unavailable
    - ``a2a_client`` — the configured Coproduct client, exposed so
      crew logs can capture endpoint + principal

    Methods not recognized delegate to the inner agent unchanged.
    """
    return _AgentWithProvenance(agent=agent, client=client)


class _AgentWithProvenance:
    """Proxy around a CrewAI-shaped agent with Coproduct A2A
    routing on ``execute_task`` + ``send_message``."""

    def __init__(self, agent: Any, client: Client) -> None:
        self._agent = agent
        self.a2a_client = client
        self.last_manifest: dict | None = None

    def send_message(self, message: str, **kwargs: Any) -> dict:
        """Route a message through A2A. Returns the server's result."""
        response = self.a2a_client.send_message(message, **kwargs)
        ext = response.get("extensions") or {}
        self.last_manifest = ext.get(EXTENSION_URI)
        return response

    def execute_task(self, task: Any) -> Any:
        """Delegate to the wrapped agent's ``execute_task`` (if any)
        and tag the last manifest from a preceding A2A call.

        This is intentionally a thin wrapper — CrewAI's own task
        engine stays authoritative. The value-add is the visible
        manifest correlation; the real Pa.Parallel enforcement
        happens server-side via the A2A extension.
        """
        if not hasattr(self._agent, "execute_task"):
            raise AttributeError("wrapped agent does not support execute_task")
        return self._agent.execute_task(task)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._agent, name)
