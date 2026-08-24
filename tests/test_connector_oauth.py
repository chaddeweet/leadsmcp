"""Tests for the Supabase-backed connector OAuth 2.0 / DCR authorization server.

These exercise connector_oauth directly (no FastMCP / no network): with Supabase
unconfigured the module uses its in-process store, so the full authorize -> token
-> bearer -> refresh flow, PKCE verification, and DCR are all covered offline.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os

import pytest

os.environ.setdefault("MCP_SECRET", "test-secret-key-for-encryption")

import connector_oauth as co


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Force the in-memory backend and a known encryption secret.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("CONNECTOR_CLIENTS", raising=False)
    monkeypatch.setenv("MCP_SECRET", "test-secret-key-for-encryption")
    co._memory_singleton._rows.clear()
    yield
    co._memory_singleton._rows.clear()


# ── PKCE ──────────────────────────────────────────────────────────────────────
def test_pkce_s256_roundtrip():
    verifier = "abc123-verifier-value-long-enough"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert co.verify_pkce(code_verifier=verifier, code_challenge=challenge, method="S256")
    assert not co.verify_pkce(code_verifier="wrong", code_challenge=challenge, method="S256")


def test_pkce_plain_and_missing():
    assert co.verify_pkce(code_verifier="xyz", code_challenge="xyz", method="plain")
    # No challenge bound -> nothing to verify.
    assert co.verify_pkce(code_verifier="", code_challenge="", method="plain")
    # Challenge present but no verifier -> fail.
    assert not co.verify_pkce(code_verifier="", code_challenge="xyz", method="plain")


# ── Metadata documents ─────────────────────────────────────────────────────────
def test_authorization_server_metadata():
    doc = co.authorization_server_metadata("https://mcp.example.com/")
    assert doc["issuer"] == "https://mcp.example.com"
    assert doc["authorization_endpoint"] == "https://mcp.example.com/authorize"
    assert doc["token_endpoint"] == "https://mcp.example.com/token"
    assert doc["registration_endpoint"] == "https://mcp.example.com/register"
    assert "S256" in doc["code_challenge_methods_supported"]


def test_protected_resource_metadata_and_challenge():
    doc = co.protected_resource_metadata("https://mcp.example.com")
    assert doc["resource"] == "https://mcp.example.com/mcp"
    assert doc["authorization_servers"] == ["https://mcp.example.com"]
    challenge = co.www_authenticate_challenge("https://mcp.example.com", error="invalid_token")
    assert challenge.startswith('Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"')
    assert 'error="invalid_token"' in challenge


# ── Dynamic Client Registration (RFC 7591) ─────────────────────────────────────
def test_dcr_public_client_no_secret():
    status, payload = run(co.register_client({
        "redirect_uris": ["https://chatgpt.com/aip/cb"],
        "token_endpoint_auth_method": "none",
        "client_name": "ChatGPT",
    }))
    assert status == 201
    assert payload["client_id"].startswith("dcr_")
    assert "client_secret" not in payload
    client = run(co.resolve_client(payload["client_id"]))
    assert client["token_endpoint_auth_method"] == "none"
    assert client["redirect_uris"] == ["https://chatgpt.com/aip/cb"]


def test_dcr_confidential_client_gets_secret():
    status, payload = run(co.register_client({
        "redirect_uris": ["https://example.com/cb"],
        "token_endpoint_auth_method": "client_secret_post",
    }))
    assert status == 201
    secret = payload["client_secret"]
    client = run(co.resolve_client(payload["client_id"]))
    assert co.validate_client_secret(client, secret)
    assert not co.validate_client_secret(client, "wrong")


def test_dcr_rejects_missing_redirect_uris():
    status, payload = run(co.register_client({"token_endpoint_auth_method": "none"}))
    assert status == 400
    assert payload["error"] == "invalid_redirect_uri"


# ── Full authorization_code + PKCE flow ─────────────────────────────────────────
def _register_public_client():
    _, payload = run(co.register_client({
        "redirect_uris": ["https://client.example/cb"],
        "token_endpoint_auth_method": "none",
    }))
    return payload["client_id"]


def test_authorization_code_flow_with_pkce():
    client_id = _register_public_client()
    verifier = "the-code-verifier-value-1234567890"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()

    code = run(co.issue_code(
        client_id=client_id,
        redirect_uri="https://client.example/cb",
        scopes=["mcp"],
        code_challenge=challenge,
        code_challenge_method="S256",
    ))
    record = run(co.consume_code(code=code))
    assert record is not None
    assert record["client_id"] == client_id
    assert co.verify_pkce(code_verifier=verifier, code_challenge=co._code_field(record, "code_challenge"), method="S256")

    # Single use: second consume returns None.
    assert run(co.consume_code(code=code)) is None

    issued = run(co.issue_token(client_id=client_id, scopes=["mcp"]))
    token_record = run(co.validate_bearer(issued["access_token"]))
    assert token_record is not None
    assert token_record["client_id"] == client_id
    assert run(co.validate_bearer("not-a-real-token")) is None


def test_refresh_token_flow():
    client_id = _register_public_client()
    issued = run(co.issue_token(client_id=client_id, scopes=["mcp"]))
    rec = run(co.find_refresh_record(refresh_token=issued["refresh_token"]))
    assert rec is not None and rec["client_id"] == client_id
    assert run(co.find_refresh_record(refresh_token="bogus")) is None


def test_expired_access_token_rejected(monkeypatch):
    client_id = _register_public_client()
    monkeypatch.setenv("CONNECTOR_TOKEN_TTL", "60")
    issued = run(co.issue_token(client_id=client_id, scopes=["mcp"]))
    # Force expiry by rewriting the stored record's expires_at into the past.
    for row in co._memory_singleton._rows:
        if row.get("kind") == "token":
            row["expires_at"] = 1
    assert run(co.validate_bearer(issued["access_token"])) is None


def test_expired_code_rejected():
    client_id = _register_public_client()
    code = run(co.issue_code(client_id=client_id, redirect_uri="https://client.example/cb", scopes=["mcp"]))
    for row in co._memory_singleton._rows:
        if row.get("kind") == "code":
            row["expires_at"] = 1
    assert run(co.consume_code(code=code)) is None


# ── Legacy static client compatibility ──────────────────────────────────────────
def test_static_client_from_env(monkeypatch):
    monkeypatch.setenv(
        "CONNECTOR_CLIENTS",
        '{"chatgpt":{"secret":"s3cr3t","name":"ChatGPT","redirect_uris":["https://chatgpt.com/aip/cb"]}}',
    )
    client = run(co.resolve_client("chatgpt"))
    assert client is not None
    assert client["token_endpoint_auth_method"] == "client_secret_post"
    assert co.validate_client_secret(client, "s3cr3t")
    assert not co.validate_client_secret(client, "nope")
    assert co.redirect_uri_registered(client, "https://chatgpt.com/aip/cb")
    assert not co.redirect_uri_registered(client, "https://evil.example/cb")


def test_enabled_flags(monkeypatch):
    monkeypatch.delenv("CONNECTOR_OAUTH_ENABLED", raising=False)
    monkeypatch.delenv("CONNECTOR_CLIENTS", raising=False)
    assert co.connector_oauth_enabled() is False
    monkeypatch.setenv("CONNECTOR_OAUTH_ENABLED", "true")
    assert co.connector_oauth_enabled() is True


# ── Supabase backend error handling (httpx.MockTransport) ───────────────────────
import httpx


def _use_supabase_backend(monkeypatch, handler):
    """Point the store at Supabase and route httpx through a mock transport."""
    monkeypatch.setenv("SUPABASE_URL", "https://mock.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key")
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def _client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(co.httpx, "AsyncClient", _client_factory)


def test_supabase_insert_success_does_not_raise(monkeypatch):
    def handler(request):
        assert request.method == "POST"
        return httpx.Response(201, text="")

    _use_supabase_backend(monkeypatch, handler)
    assert co._supabase_configured() is True
    # Should complete without raising (register performs an insert).
    status, payload = run(co.register_client({
        "redirect_uris": ["https://client.example/cb"],
        "token_endpoint_auth_method": "none",
    }))
    assert status == 201
    assert payload["client_id"].startswith("dcr_")


def test_supabase_permission_denied_raises_store_error(monkeypatch):
    def handler(request):
        return httpx.Response(
            403,
            json={"message": "permission denied for table connector_oauth", "code": "42501"},
        )

    _use_supabase_backend(monkeypatch, handler)
    with pytest.raises(co.StoreError) as excinfo:
        run(co.register_client({
            "redirect_uris": ["https://client.example/cb"],
            "token_endpoint_auth_method": "none",
        }))
    assert excinfo.value.status == 403
    assert "permission denied for table connector_oauth" in excinfo.value.detail


def test_supabase_unreachable_raises_store_error_503(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    _use_supabase_backend(monkeypatch, handler)
    with pytest.raises(co.StoreError) as excinfo:
        run(co.register_client({
            "redirect_uris": ["https://client.example/cb"],
            "token_endpoint_auth_method": "none",
        }))
    assert excinfo.value.status == 503


def test_validate_bearer_fails_closed_on_store_error(monkeypatch):
    def handler(request):
        return httpx.Response(500, json={"message": "boom"})

    _use_supabase_backend(monkeypatch, handler)
    # A store outage must never authenticate a bearer token.
    assert run(co.validate_bearer("some-token")) is None
