"""HTTP client for Coproduct A2A.

Minimal surface: construct a :class:`Client`, call
:meth:`Client.send_message` or :meth:`Client.get_task`, and read the
result. The server-side provable-coordination manifest is verified
automatically when `verify_on_receive=True` (default).
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from coproduct_a2a.constants import EXTENSION_URI, JWT_ALG
from coproduct_a2a.verify import InvalidSignature, verify_manifest


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _now_ms() -> int:
    return int(time.time() * 1000)


def mint_bearer_token(
    signing_seed: bytes,
    principal: str,
    capabilities: Sequence[str] = (),
    ttl_ms: int = 15 * 60 * 1000,
) -> str:
    """Mint an EdDSA JWT bearer token matching the Rust server's
    `verify_token` expectations.

    `signing_seed` is the 32-byte ed25519 private seed. Keep it out
    of source control — fetch from Fly secrets or a secrets manager.
    """
    if not isinstance(signing_seed, (bytes, bytearray)) or len(signing_seed) != 32:
        raise ValueError("signing_seed must be 32 bytes")
    priv = Ed25519PrivateKey.from_private_bytes(bytes(signing_seed))
    header = {"alg": JWT_ALG, "typ": "JWT"}
    now = _now_ms()
    payload = {
        "sub": principal,
        "caps": list(capabilities),
        "exp": now + int(ttl_ms),
        "iat": now,
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode()
    )
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = priv.sign(signing_input)
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


@dataclass
class Client:
    """HTTP client for a Coproduct A2A server.

    Auto-verification of the provable-coordination manifest is on
    by default; pass ``verify_on_receive=False`` to skip (useful for
    tests that want to inspect bad signatures).
    """

    endpoint: str
    token: Optional[str] = None
    server_public_key: Optional[bytes] = None
    verify_on_receive: bool = True
    timeout: float = 30.0
    _http: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        headers = {"content-type": "application/json"}
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        self._http = httpx.Client(headers=headers, timeout=self.timeout)

    @classmethod
    def from_env(cls) -> "Client":
        """Build a client from the canonical env vars.

        Reads:
            COPRODUCT_A2A_ENDPOINT    — full URL, e.g. https://coproduct-a2a.fly.dev/a2a
            COPRODUCT_A2A_TOKEN       — pre-minted bearer JWT (optional)
            COPRODUCT_A2A_PUBLIC_KEY  — base64url ed25519 pubkey (for verify)
        """
        endpoint = os.environ.get("COPRODUCT_A2A_ENDPOINT")
        if not endpoint:
            raise RuntimeError("COPRODUCT_A2A_ENDPOINT not set")
        token = os.environ.get("COPRODUCT_A2A_TOKEN") or None
        pk_env = os.environ.get("COPRODUCT_A2A_PUBLIC_KEY")
        pk = None
        if pk_env:
            pad = "=" * (-len(pk_env) % 4)
            pk = base64.urlsafe_b64decode(pk_env + pad)
        return cls(endpoint=endpoint, token=token, server_public_key=pk)

    # ─── methods ────────────────────────────────────────────────

    def send_message(self, message: str, session_id: Optional[str] = None) -> dict:
        """Call `message/send` on the A2A server."""
        params: dict = {"message": message}
        if session_id is not None:
            params["session_id"] = session_id
        return self._call("message/send", params)

    def get_task(self, task_id: str) -> dict:
        """Call `tasks/get`."""
        return self._call("tasks/get", {"task_id": task_id})

    def cancel_task(self, task_id: str) -> dict:
        """Call `tasks/cancel`."""
        return self._call("tasks/cancel", {"task_id": task_id})

    def agent_card(self) -> dict:
        """Fetch the Agent Card via `agent/getAuthenticatedExtendedCard`."""
        return self._call("agent/getAuthenticatedExtendedCard", None)

    # ─── internals ──────────────────────────────────────────────

    def _call(self, method: str, params: Optional[Mapping[str, Any]]) -> dict:
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "id": str(uuid.uuid4()),
        }
        if params is not None:
            req["params"] = dict(params)
        resp = self._http.post(self.endpoint, json=req)
        resp.raise_for_status()
        payload = resp.json()
        if self.verify_on_receive and payload.get("error") is None:
            if self.server_public_key:
                ext = payload.get("extensions") or {}
                if EXTENSION_URI in ext:
                    # Raises InvalidSignature on failure.
                    verify_manifest(payload, self.server_public_key)
        return payload

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
