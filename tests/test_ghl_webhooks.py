import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import ghl_webhooks


def test_ed25519_webhook_signature_verification(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    monkeypatch.setenv("GHL_WEBHOOK_ED25519_PUBLIC_KEY", public_pem)
    raw_body = b'{"type":"INSTALL","webhookId":"evt_1"}'
    signature = base64.b64encode(private_key.sign(raw_body)).decode("ascii")

    assert ghl_webhooks.verify_ghl_signature(raw_body, signature) is True
    assert ghl_webhooks.verify_ghl_signature(raw_body + b" ", signature) is False


def test_webhook_event_id_prefers_supplied_id():
    assert (
        ghl_webhooks.webhook_event_id(
            {"webhookId": "evt_123"},
            b"body",
        )
        == "evt_123"
    )

