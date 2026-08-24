"""Tests for Outscraper request defaults, retry wiring, and per-tool behaviour."""
import httpx
import pytest

from servers import http_retry, outscraper_server


class _Resp:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._payload


def _install_fake_client(monkeypatch, responses):
    """Replace httpx.AsyncClient; capture calls and return queued responses."""
    calls: list[dict] = []
    seq = list(responses)

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None, params=None):
            calls.append({"method": "GET", "url": url, "headers": headers, "params": params})
            item = seq[len(calls) - 1]
            if isinstance(item, Exception):
                raise item
            return item

        async def post(self, url, headers=None, json=None):
            calls.append({"method": "POST", "url": url, "headers": headers, "json": json})
            item = seq[len(calls) - 1]
            if isinstance(item, Exception):
                raise item
            return item

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    return calls


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    async def _s(_):
        return None

    monkeypatch.setattr(http_retry.asyncio, "sleep", _s)
    monkeypatch.setattr(http_retry.random, "uniform", lambda lo, hi: 0.0)
    monkeypatch.setenv("OUTSCRAPER_API_KEY", "test-key")


# ── async/ui defaults ─────────────────────────────────────────────────────────

def test_defaults_force_async_and_ui_false():
    out = outscraper_server._with_outscraper_defaults({"query": "x"})
    assert out["async"] == "false"
    assert out["ui"] == "false"


def test_defaults_override_caller_supplied_true():
    # Enforced, not merely defaulted: caller cannot opt into async/ui.
    out = outscraper_server._with_outscraper_defaults({"async": "true", "ui": "true"})
    assert out["async"] == "false"
    assert out["ui"] == "false"


async def test_get_sends_defaults_and_auth_header(monkeypatch):
    calls = _install_fake_client(monkeypatch, [_Resp(payload={"ok": True})])
    result = await outscraper_server._get("/google-maps-search", {"query": "plumbers"})
    assert result == {"ok": True}
    assert calls[0]["params"]["async"] == "false"
    assert calls[0]["params"]["ui"] == "false"
    assert calls[0]["headers"]["X-API-KEY"] == "test-key"


async def test_post_sends_defaults_and_auth_header(monkeypatch):
    calls = _install_fake_client(monkeypatch, [_Resp(payload={"ok": True})])
    await outscraper_server._post("/email-validator", {"query": "a@b.com"})
    assert calls[0]["json"]["async"] == "false"
    assert calls[0]["json"]["ui"] == "false"
    assert calls[0]["headers"]["X-API-KEY"] == "test-key"
    assert calls[0]["headers"]["Content-Type"] == "application/json"


# ── retry wiring through the real _get ───────────────────────────────────────

async def test_get_retries_on_429(monkeypatch):
    calls = _install_fake_client(
        monkeypatch,
        [_Resp(status_code=429, headers={"Retry-After": "1"}), _Resp(payload={"done": 1})],
    )
    result = await outscraper_server._get("/google-search", {"query": "x"})
    assert result == {"done": 1}
    assert len(calls) == 2


async def test_get_retries_on_network_error(monkeypatch):
    calls = _install_fake_client(
        monkeypatch, [httpx.ConnectError("boom"), _Resp(payload={"done": 1})]
    )
    result = await outscraper_server._get("/geocoding", {"query": "x"})
    assert result == {"done": 1}
    assert len(calls) == 2


async def test_get_does_not_retry_client_error(monkeypatch):
    calls = _install_fake_client(monkeypatch, [_Resp(status_code=400)])
    with pytest.raises(httpx.HTTPStatusError):
        await outscraper_server._get("/google-search", {"query": "x"})
    assert len(calls) == 1


# ── auth error surfaced without leaking the key ──────────────────────────────

async def test_missing_key_raises_before_request(monkeypatch):
    monkeypatch.delenv("OUTSCRAPER_API_KEY", raising=False)
    calls = _install_fake_client(monkeypatch, [_Resp()])
    with pytest.raises(RuntimeError, match="Missing Outscraper API key"):
        await outscraper_server._get("/google-search", {"query": "x"})
    assert calls == []  # never hit the network


# ── a representative tool end-to-end ─────────────────────────────────────────

async def test_google_maps_search_tool(monkeypatch):
    calls = _install_fake_client(monkeypatch, [_Resp(payload={"data": []})])
    result = await outscraper_server.google_maps_search(query="dentists, Cape Town, ZA", limit=5)
    assert result == {"data": []}
    assert calls[0]["url"].endswith("/google-maps-search")
    assert calls[0]["params"]["query"] == "dentists, Cape Town, ZA"
    assert calls[0]["params"]["async"] == "false"
    assert calls[0]["params"]["ui"] == "false"
