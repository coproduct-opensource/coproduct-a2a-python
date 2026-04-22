"""Signature verification for Coproduct provable-coordination manifests.

Reproduces the Rust server's signing pipeline byte-for-byte:

1. Take the manifest dict.
2. Zero the ``signature`` field.
3. JCS-canonicalize (RFC 8785).
4. Verify the detached ed25519 signature against a known public key.

Equal bytes on both sides of the language barrier is the only way
cross-language sign/verify works; our JCS implementation
(`coproduct_a2a.jcs`) is the minimal subset needed to match
``serde_jcs`` output on manifests.
"""

from __future__ import annotations

import base64
import copy
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature as _CryptoInvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from coproduct_a2a.constants import EXTENSION_URI
from coproduct_a2a.jcs import canonicalize


class InvalidSignature(Exception):
    """Raised when a manifest's signature does not verify.

    Callers that wrap or log this exception should never retry —
    the bytes on the wire did not come from the claimed signer.
    """


def _b64url_decode(s: str) -> bytes:
    """Decode a base64url string with optional padding."""
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def verify_manifest(
    response_or_manifest: Mapping[str, Any],
    public_key_bytes: bytes,
) -> dict:
    """Verify a manifest and return it as a plain dict.

    Accepts either the full JSON-RPC response (in which case the
    manifest is extracted from ``extensions[EXTENSION_URI]``) or the
    manifest dict directly. Returns the manifest dict on success.

    Raises:
        InvalidSignature: signature didn't verify OR manifest has
            no ``signature`` field OR public key is malformed.
        KeyError: response has no manifest at the expected URI.
    """
    if not isinstance(public_key_bytes, (bytes, bytearray)) or len(public_key_bytes) != 32:
        raise InvalidSignature("public key must be 32 bytes of ed25519")

    manifest = _extract_manifest(response_or_manifest)

    signature_str = manifest.get("signature")
    if not isinstance(signature_str, str) or not signature_str.startswith("ed25519:"):
        raise InvalidSignature("manifest missing ed25519: signature")
    sig_b64 = signature_str[len("ed25519:") :]
    try:
        sig_bytes = _b64url_decode(sig_b64)
    except Exception as exc:
        raise InvalidSignature(f"base64url decode: {exc}") from exc
    if len(sig_bytes) != 64:
        raise InvalidSignature(
            f"ed25519 signature must be 64 bytes; got {len(sig_bytes)}"
        )

    # Zero the signature field and canonicalize. This is what the
    # Rust server signed.
    for_sign = copy.deepcopy(dict(manifest))
    for_sign["signature"] = ""
    try:
        canonical = canonicalize(for_sign)
    except Exception as exc:
        raise InvalidSignature(f"canonicalize: {exc}") from exc

    try:
        key = Ed25519PublicKey.from_public_bytes(bytes(public_key_bytes))
    except Exception as exc:
        raise InvalidSignature(f"ed25519 pubkey: {exc}") from exc

    try:
        key.verify(sig_bytes, canonical)
    except _CryptoInvalidSignature as exc:
        raise InvalidSignature("signature did not verify") from exc

    return dict(manifest)


def _extract_manifest(value: Mapping[str, Any]) -> Mapping[str, Any]:
    # Full response shape: top-level `extensions` dict keyed by URI.
    ext = value.get("extensions")
    if isinstance(ext, dict) and EXTENSION_URI in ext:
        return ext[EXTENSION_URI]
    # Manifest shape: carries `manifest_version` directly.
    if "manifest_version" in value:
        return value
    raise KeyError(
        f"response does not contain the {EXTENSION_URI} extension payload"
    )
