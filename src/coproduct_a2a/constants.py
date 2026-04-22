"""Stable identifiers used by the provable-coordination extension.

Kept in a tiny dedicated module so adapter modules
(`coproduct_a2a.langgraph`, `coproduct_a2a.crewai`) can import the
URI without pulling in the httpx / cryptography deps of `client.py`.
"""

#: Stable URI of the provable-coordination extension. Matches
#: `https://coproduct.one/ext/provable-coordination/v1` served by
#: the Rust reference implementation. Must end in `/v1` — breaking
#: changes get a new URI (/v2, ...).
EXTENSION_URI = "https://coproduct.one/ext/provable-coordination/v1"

#: The manifest version this SDK speaks. Servers on the same
#: `/v1` URI return `manifest_version == "1"`.
MANIFEST_VERSION = "1"

#: JWT signing algorithm — Ed25519 per RFC 8037.
JWT_ALG = "EdDSA"

#: HTTP header Fly's TLS terminator uses for mTLS client certs.
MTLS_HEADER = "Fly-Forwarded-Client-Cert"
