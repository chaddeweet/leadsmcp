import main


def test_callback_token_response_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("GHL_OAUTH_ALLOW_TOKEN_RESPONSE", raising=False)
    monkeypatch.delenv(
        "GHL_OAUTH_ALLOW_TOKEN_RESPONSE_IN_PRODUCTION",
        raising=False,
    )

    assert main._allow_callback_token_response() is False


def test_callback_token_response_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("GHL_OAUTH_ALLOW_TOKEN_RESPONSE", "true")

    assert main._allow_callback_token_response() is True
