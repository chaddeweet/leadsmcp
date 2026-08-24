"""HighLevel webhook authenticity and event identity helpers."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key


DEFAULT_GHL_ED25519_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAi2HR1srL4o18O8BRa7gVJY7G7bupbN3H9AwJrHCDiOg=
-----END PUBLIC KEY-----"""


def verify_ghl_signature(raw_body: bytes, signature: str) -> bool:
    """Verify the current X-GHL-Signature Ed25519 signature."""
    if not signature or signature == "N/A":
        return False
    public_key_pem = os.getenv(
        "GHL_WEBHOOK_ED25519_PUBLIC_KEY",
        DEFAULT_GHL_ED25519_PUBLIC_KEY,
    ).encode("utf-8")
    try:
        public_key = load_pem_public_key(public_key_pem)
        public_key.verify(base64.b64decode(signature), raw_body)
    except (ValueError, TypeError, InvalidSignature):
        return False
    return True


def webhook_event_id(payload: dict, raw_body: bytes) -> str:
    supplied = str(payload.get("webhookId") or "").strip()
    if supplied:
        return supplied
    return hashlib.sha256(raw_body).hexdigest()

