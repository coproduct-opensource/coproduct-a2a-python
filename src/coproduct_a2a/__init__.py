"""Python SDK for Coproduct A2A.

Exports:
    Client                — HTTP client for the A2A JSON-RPC endpoint
    verify_manifest       — verify server's provenance manifest signature
    mint_bearer_token     — client-side OAuth 2.0 bearer token minting
    InvalidSignature      — raised when manifest signature doesn't verify
    EXTENSION_URI         — stable URI of the provable-coordination extension
"""

from coproduct_a2a.client import Client, mint_bearer_token
from coproduct_a2a.verify import InvalidSignature, verify_manifest
from coproduct_a2a.constants import EXTENSION_URI

__all__ = [
    "Client",
    "verify_manifest",
    "mint_bearer_token",
    "InvalidSignature",
    "EXTENSION_URI",
]

__version__ = "0.1.0"
