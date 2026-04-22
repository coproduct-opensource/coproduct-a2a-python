"""Tests for client-side bearer-token minting.

The token must be accepted by the Rust server's `verify_token`
function. We can't run the Rust server from pytest, but we can
verify the token structurally + sign-check it locally using the
same cryptography primitives the server uses.
"""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from coproduct_a2a import mint_bearer_token
from coproduct_a2a.constants import JWT_ALG


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def test_mint_produces_three_segments():
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw()
    token = mint_bearer_token(seed, "alice", ["read:x"])
    assert token.count(".") == 2


def test_header_is_eddsa_jwt():
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw()
    token = mint_bearer_token(seed, "alice")
    header_b64 = token.split(".")[0]
    header = json.loads(_b64url_decode(header_b64))
    assert header == {"alg": JWT_ALG, "typ": "JWT"}


def test_payload_contains_sub_and_caps():
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw()
    caps = ["read:workspace/alice", "delegate:reporter"]
    token = mint_bearer_token(seed, "alice", caps, ttl_ms=60_000)
    payload_b64 = token.split(".")[1]
    payload = json.loads(_b64url_decode(payload_b64))
    assert payload["sub"] == "alice"
    assert payload["caps"] == caps
    assert payload["exp"] > payload["iat"]
    assert payload["exp"] - payload["iat"] == 60_000


def test_signature_verifies_against_pubkey():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes_raw()
    seed = priv.private_bytes_raw()
    token = mint_bearer_token(seed, "alice")
    header_b64, payload_b64, sig_b64 = token.split(".")
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = _b64url_decode(sig_b64)
    # Round-trip the pub key through the public_bytes → from_public_bytes
    # path so we're not accidentally verifying with the same object.
    pk = Ed25519PublicKey.from_public_bytes(pub)
    pk.verify(sig, signing_input)  # raises if bad


def test_rejects_short_seed():
    with pytest.raises(ValueError):
        mint_bearer_token(b"too-short", "alice")


def test_ttl_zero_mints_expired_token():
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw()
    token = mint_bearer_token(seed, "alice", ttl_ms=0)
    payload_b64 = token.split(".")[1]
    payload = json.loads(_b64url_decode(payload_b64))
    assert payload["exp"] == payload["iat"]
