import pytest

import main


def test_installation_cookie_round_trip(monkeypatch):
    monkeypatch.setenv("GHL_OAUTH_STATE_SECRET", "test-secret")

    value = main._sign_installation_cookie("company:location")
    payload = main._verify_installation_cookie(value)

    assert payload["install_key"] == "company:location"


def test_installation_cookie_rejects_tampering(monkeypatch):
    monkeypatch.setenv("GHL_OAUTH_STATE_SECRET", "test-secret")
    value = main._sign_installation_cookie("company:location")

    with pytest.raises(ValueError, match="signature"):
        main._verify_installation_cookie(value + "tampered")
