"""Tests for manifest signature verification.

Uses cryptography.hazmat's ed25519 to generate a keypair locally,
signs a manifest the same way the Rust server would (zero the
signature, JCS-canonicalize, ed25519-sign, base64url-encode), and
verifies via :func:`verify_manifest`. Negative cases cover the
tamper / wrong-key / malformed-signature paths.
"""

from __future__ import annotations

import base64
import copy

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from coproduct_a2a import InvalidSignature, verify_manifest
from coproduct_a2a.constants import EXTENSION_URI, MANIFEST_VERSION
from coproduct_a2a.jcs import canonicalize


def _sign_manifest_like_rust(manifest: dict, priv: Ed25519PrivateKey) -> dict:
    """Sign a manifest the same way the Rust `sign_in_place` does:
    zero `signature`, JCS-canonicalize, ed25519-sign, prefix `ed25519:`.
    """
    for_sign = copy.deepcopy(manifest)
    for_sign["signature"] = ""
    canonical = canonicalize(for_sign)
    sig = priv.sign(canonical)
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    out = copy.deepcopy(manifest)
    out["signature"] = f"ed25519:{sig_b64}"
    return out


def _fresh_keypair():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes_raw()
    return priv, pub


def _sample_manifest() -> dict:
    return {
        "manifest_version": MANIFEST_VERSION,
        "provenance_trail": [
            {
                "source": "a2a:inbound/message/send",
                "timestamp_ms": 1776963010123,
                "acting_agent": "agent:alice",
                "capability": "message/send",
            }
        ],
        "capability_envelope_sha": "",
        "cohort_witnesses": [],
        "hydrate_log_rev": 1,
        "signature": "",
    }


def test_sign_then_verify_roundtrips():
    priv, pub = _fresh_keypair()
    manifest = _sign_manifest_like_rust(_sample_manifest(), priv)
    result = verify_manifest(manifest, pub)
    assert result["hydrate_log_rev"] == 1


def test_tampered_manifest_rejected():
    priv, pub = _fresh_keypair()
    manifest = _sign_manifest_like_rust(_sample_manifest(), priv)
    manifest["hydrate_log_rev"] = 999  # tamper
    with pytest.raises(InvalidSignature):
        verify_manifest(manifest, pub)


def test_wrong_key_rejected():
    priv, _ = _fresh_keypair()
    _, other_pub = _fresh_keypair()
    manifest = _sign_manifest_like_rust(_sample_manifest(), priv)
    with pytest.raises(InvalidSignature):
        verify_manifest(manifest, other_pub)


def test_missing_signature_rejected():
    manifest = _sample_manifest()  # signature is ""
    _, pub = _fresh_keypair()
    with pytest.raises(InvalidSignature):
        verify_manifest(manifest, pub)


def test_wrong_prefix_rejected():
    priv, pub = _fresh_keypair()
    manifest = _sign_manifest_like_rust(_sample_manifest(), priv)
    sig = manifest["signature"]
    manifest["signature"] = sig.replace("ed25519:", "rs256:")
    with pytest.raises(InvalidSignature):
        verify_manifest(manifest, pub)


def test_bad_signature_length_rejected():
    _, pub = _fresh_keypair()
    manifest = _sample_manifest()
    # 32-byte junk base64'd → will fail length check (not 64).
    junk = base64.urlsafe_b64encode(b"x" * 32).rstrip(b"=").decode("ascii")
    manifest["signature"] = f"ed25519:{junk}"
    with pytest.raises(InvalidSignature):
        verify_manifest(manifest, pub)


def test_bad_pubkey_length_rejected():
    priv, _ = _fresh_keypair()
    manifest = _sign_manifest_like_rust(_sample_manifest(), priv)
    with pytest.raises(InvalidSignature):
        verify_manifest(manifest, b"\x00" * 31)  # 31 bytes — wrong


def test_accepts_full_response_shape():
    priv, pub = _fresh_keypair()
    manifest = _sign_manifest_like_rust(_sample_manifest(), priv)
    response = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "result": {"id": "task-1", "state": "submitted"},
        "extensions": {EXTENSION_URI: manifest},
    }
    result = verify_manifest(response, pub)
    assert result["manifest_version"] == MANIFEST_VERSION


def test_response_without_manifest_raises_keyerror():
    response = {
        "jsonrpc": "2.0",
        "id": "x",
        "result": {},
        "extensions": {"https://other/ext/foo/v1": {}},
    }
    _, pub = _fresh_keypair()
    with pytest.raises(KeyError):
        verify_manifest(response, pub)


def test_missing_extensions_key_raises_keyerror():
    response = {"jsonrpc": "2.0", "id": "x", "result": {}}
    _, pub = _fresh_keypair()
    with pytest.raises(KeyError):
        verify_manifest(response, pub)
