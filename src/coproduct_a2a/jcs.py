"""JSON Canonicalization Scheme (RFC 8785) — minimal implementation.

Only handles the JSON subset that the provable-coordination manifest
uses: objects, arrays, strings, integers, and booleans. Floats and
other RFC 8785 corner cases are out of scope; the Rust server never
emits them in manifests.

Consistency with the Rust crate's `serde_jcs` output is the
invariant that makes cross-language signature verification work.
The verify tests round-trip a manifest serialized by the Rust server
and re-canonicalized here.
"""

from __future__ import annotations

import json


def canonicalize(value: object) -> bytes:
    """Return the RFC 8785 canonical JSON form of `value` as bytes.

    Rules (subset sufficient for the manifest types):

    - object keys sorted lexicographically by codepoint (RFC 8785
      § 3.2.3)
    - no insignificant whitespace
    - strings encoded with JSON escapes, UTF-8 output
    - integers emitted as decimal digits with no sign / leading
      zeros
    - booleans as `true` / `false`; null as `null`
    """
    return _emit(value).encode("utf-8")


def _emit(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # json.dumps yields RFC-compliant escapes; ensure_ascii=False
        # keeps Unicode as UTF-8 encoded characters (matching JCS).
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts = [_emit(v) for v in value]
        return "[" + ",".join(parts) + "]"
    if isinstance(value, dict):
        # Sort by codepoint. UTF-16 vs codepoint sorting: for ASCII
        # manifest keys this is identical; non-ASCII keys aren't
        # used in our schema.
        items = sorted(value.items(), key=lambda kv: kv[0])
        parts = [f"{_emit(k)}:{_emit(v)}" for k, v in items]
        return "{" + ",".join(parts) + "}"
    if isinstance(value, float):
        # Floats aren't part of the manifest schema; reject rather
        # than silently pick an encoding that might diverge from
        # serde_jcs.
        raise ValueError("floats not supported in this JCS subset")
    raise ValueError(f"unsupported JSON value type: {type(value).__name__}")
