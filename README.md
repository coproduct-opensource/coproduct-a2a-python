# `coproduct-a2a` — Python SDK for Coproduct A2A

Client for the [`coproduct.provable-coordination.v1`](https://coproduct.one/ext/provable-coordination/v1) A2A extension. Mints bearer tokens, calls A2A methods, **verifies the server's signed provenance manifest** on every response.

## Why this exists

An A2A agent that declares the `coproduct.provable-coordination.v1` extension in its Agent Card gets three guarantees added to every response:

- **Provenance trail** — signed lineage back to inputs, acting agent, capability
- **Capability envelope** — calls are bounded by declared capabilities
- **Cohort witnesses** — Pa.Parallel I1–I7 invariants attested on every call

This SDK is the 5-line integration that makes those guarantees visible to Python agents.

## Install

```bash
pip install coproduct-a2a
# or, with uv:
uv add coproduct-a2a
```

## Quickstart — LangGraph

```python
from coproduct_a2a import Client, verify_manifest

client = Client.from_env()  # reads COPRODUCT_A2A_{ENDPOINT,PUBLIC_KEY,TOKEN}
response = client.send_message("hello, agent!")
manifest = verify_manifest(response, client.server_public_key)
print(f"Task {response['result']['id']} at rev {manifest['hydrate_log_rev']}")
```

That's it. Five lines. The `verify_manifest` call raises `InvalidSignature` if the server returned anything the declared pubkey didn't sign.

## LangGraph adapter

```python
from langgraph.graph import StateGraph
from coproduct_a2a.langgraph import ProvableCoordinationNode

graph = StateGraph(AgentState)
graph.add_node("agent", ProvableCoordinationNode(client))
```

The node wraps the message/send call; incoming state gets mapped to A2A params; the response's manifest is attached to the outgoing state as `state.provenance_manifest`.

## CrewAI wrapper

```python
from crewai import Agent
from coproduct_a2a.crewai import wrap_agent_with_provenance

agent = Agent(role="Reporter", goal="Summarize the workspace")
wrapped = wrap_agent_with_provenance(agent, client)
```

Every tool invocation threads through the provable-coordination extension; the crew log gains signed manifests it can audit.

## Manifest fields

The verified manifest dict carries:

| Field | Type | Meaning |
|---|---|---|
| `manifest_version` | `"1"` | Pinned to this extension URI |
| `provenance_trail` | `list[ProvenanceStep]` | Ordered steps citing data sources |
| `capability_envelope_sha` | `str` | SHA-256 of the declared envelope |
| `cohort_witnesses` | `list[CohortWitness]` | Pa.Parallel I1–I7 attestations |
| `hydrate_log_rev` | `int` | Monotonic server-state revision |
| `signature` | `str` | `ed25519:<base64url>` over JCS-canonicalized payload |

## Reference deployment

[`coproduct.fly.dev`](https://coproduct.fly.dev) is a live instance running the A2A server this SDK talks to. Point `COPRODUCT_A2A_ENDPOINT=https://coproduct.fly.dev/a2a` to integration-test against it. The `/aha` page on that host is a browser-based tamper playground for the same manifest verification this SDK does in Python.

## See also

- [`coproduct-a2a`](https://github.com/coproduct-opensource/coproduct-a2a) — Rust A2A server (the reference this SDK verifies against)
- [`coproduct-demo-a2a-langgraph`](https://github.com/coproduct-opensource/coproduct-demo-a2a-langgraph) — LangGraph state graph using this SDK end-to-end
- [`coproduct-demo-ragkit`](https://github.com/coproduct-opensource/coproduct-demo-ragkit) · [`coproduct-demo-taskhub`](https://github.com/coproduct-opensource/coproduct-demo-taskhub) — 5-agent companion demos
- [`coproduct.provable-coordination.v1` spec](https://coproduct.fly.dev/ext/provable-coordination/v1)

## Releasing

Releases are published to PyPI via GitHub Actions trusted-publisher OIDC — no API token stored in this repo. To cut a release:

1. Bump `[project].version` in `pyproject.toml`.
2. Commit + push to `main`.
3. Tag with `v<version>` and push the tag: `git tag v0.2.0 && git push origin v0.2.0`.
4. Create a GitHub Release from that tag (via the web UI or `gh release create v0.2.0 --generate-notes`).

The `publish` workflow builds `dist/`, smoke-tests the wheel, and uploads to PyPI. See `.github/workflows/publish.yml`.

First-time setup: PyPI trusted-publisher config must exist. See the `pypi` GitHub Actions environment for the configuration.

## License

MIT — see [LICENSE](LICENSE).
