"""Tests for per-request Outscraper credential resolution.

Covers header extraction, missing-credential error, env fallback,
header-over-env precedence, and downstream ``X-API-KEY`` forwarding.
"""
import contextlib

import httpx
import pytest
from starlette.requests import Request

from fastmcp.server.http import set_http_request

from servers import outscraper_server


def _request_with_headers(headers: dict[str, str]) -> Request:
    """Build a minimal Starlette Request carrying the given headers."""
    raw_headers = [
        (name.encode("latin-1"), value.encode("latin-1"))
        for name, value in headers.items()
    ]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": raw_headers,
            "client": None,
            "server": None,
            "root_path": "",
        }
    )


@contextlib.contextmanager
def _http_context(headers: dict[str, str]):
    with set_http_request(_request_with_headers(headers)):
        yield


def test_resolves_key_from_header():
    with _http_context({"x-api-key": "header-key-123"}):
        assert outscraper_server._resolve_api_key() == "header-key-123"


def test_header_value_is_stripped():
    with _http_context({"x-api-key": "  spaced-key  "}):
        assert outscraper_server._resolve_api_key() == "spaced-key"


def test_missing_credential_raises_clear_error(monkeypatch):
    monkeypatch.delenv("OUTSCRAPER_API_KEY", raising=False)
    with _http_context({}):
        with pytest.raises(RuntimeError, match="Missing Outscraper API key"):
            outscraper_server._resolve_api_key()


def test_missing_credential_error_does_not_leak_key(monkeypatch):
    monkeypatch.delenv("OUTSCRAPER_API_KEY", raising=False)
    with _http_context({}):
        with pytest.raises(RuntimeError) as exc:
            outscraper_server._resolve_api_key()
    message = str(exc.value)
    assert "x-api-key" in message
    assert "OUTSCRAPER_API_KEY" in message


def test_env_fallback_when_no_header(monkeypatch):
    monkeypatch.setenv("OUTSCRAPER_API_KEY", "env-key-456")
    with _http_context({}):
        assert outscraper_server._resolve_api_key() == "env-key-456"


def test_env_fallback_without_http_context(monkeypatch):
    """No active HTTP request -> get_http_headers returns {} -> env fallback."""
    monkeypatch.setenv("OUTSCRAPER_API_KEY", "env-key-789")
    assert outscraper_server._resolve_api_key() == "env-key-789"


def test_header_takes_precedence_over_env(monkeypatch):
    monkeypatch.setenv("OUTSCRAPER_API_KEY", "env-key-should-lose")
    with _http_context({"x-api-key": "header-key-wins"}):
        assert outscraper_server._resolve_api_key() == "header-key-wins"


def test_blank_header_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("OUTSCRAPER_API_KEY", "env-key-used")
    with _http_context({"x-api-key": "   "}):
        assert outscraper_server._resolve_api_key() == "env-key-used"


def test_headers_dict_uses_resolved_key():
    with _http_context({"x-api-key": "resolved-key"}):
        assert outscraper_server._headers() == {"X-API-KEY": "resolved-key"}


@pytest.mark.asyncio
async def test_downstream_get_forwards_x_api_key(monkeypatch):
    """The resolved key must be sent to Outscraper as the X-API-KEY header."""
    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None, params=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    with _http_context({"x-api-key": "downstream-key"}):
        result = await outscraper_server._get("/google-maps-search", {"query": "x"})

    assert result == {"ok": True}
    assert captured["headers"]["X-API-KEY"] == "downstream-key"
    assert captured["url"].endswith("/google-maps-search")


@pytest.mark.asyncio
async def test_downstream_post_forwards_x_api_key(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    with _http_context({"x-api-key": "post-key"}):
        result = await outscraper_server._post("/email-validator", {"query": "a@b.com"})

    assert result == {"ok": True}
    assert captured["headers"]["X-API-KEY"] == "post-key"
    assert captured["headers"]["Content-Type"] == "application/json"
