"""Tests for the Stripe billing sub-server: auth, retries, and safe-retry gating."""
import httpx
import pytest

from servers import http_retry, stripe_server


class _Resp:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text

    @property
    def is_error(self):
        return self.status_code >= 400

    def json(self):
        return self._payload


def _install_fake_client(monkeypatch, responses):
    calls: list[dict] = []
    seq = list(responses)

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, auth=None, data=None, params=None, headers=None):
            calls.append(
                {"method": method, "url": url, "auth": auth, "data": data,
                 "params": params, "headers": headers}
            )
            item = seq[len(calls) - 1]
            if isinstance(item, Exception):
                raise item
            return item

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    return calls


@pytest.fixture(autouse=True)
def _env_and_fast_sleep(monkeypatch):
    async def _s(_):
        return None

    monkeypatch.setattr(http_retry.asyncio, "sleep", _s)
    monkeypatch.setattr(http_retry.random, "uniform", lambda lo, hi: 0.0)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")


# ── auth / config ─────────────────────────────────────────────────────────────

async def test_missing_secret_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    calls = _install_fake_client(monkeypatch, [_Resp(payload={"id": "x"})])
    with pytest.raises(ValueError, match="STRIPE_SECRET_KEY"):
        await stripe_server._stripe_request("GET", "/customers")
    assert calls == []  # never hit the network


async def test_uses_basic_auth_with_secret(monkeypatch):
    calls = _install_fake_client(monkeypatch, [_Resp(payload={"id": "cus_1"})])
    await stripe_server._stripe_request("GET", "/customers", params={"limit": 1})
    assert calls[0]["auth"] == ("sk_test_123", "")
    assert "Stripe-Version" in calls[0]["headers"]


async def test_error_response_maps_to_runtime_error(monkeypatch):
    _install_fake_client(
        monkeypatch,
        [_Resp(status_code=402, payload={"error": {"message": "Card declined"}})],
    )
    with pytest.raises(RuntimeError, match="Stripe API 402: Card declined"):
        await stripe_server._stripe_request("GET", "/customers")


# ── retry gating (idempotency safety) ────────────────────────────────────────

async def test_get_retries_on_429(monkeypatch):
    calls = _install_fake_client(
        monkeypatch,
        [_Resp(status_code=429, headers={"Retry-After": "1"}), _Resp(payload={"id": "cus_1"})],
    )
    result = await stripe_server._stripe_request("GET", "/customers")
    assert result == {"id": "cus_1"}
    assert len(calls) == 2


async def test_post_without_idempotency_key_is_not_retried(monkeypatch):
    # A keyless write must NOT be retried — retrying could double-create/charge.
    calls = _install_fake_client(monkeypatch, [_Resp(status_code=429), _Resp(payload={"id": "x"})])
    with pytest.raises(RuntimeError, match="Stripe API 429"):
        await stripe_server._stripe_request("POST", "/customers", data={"email": "a@b.com"})
    assert len(calls) == 1


async def test_post_with_idempotency_key_is_retried(monkeypatch):
    calls = _install_fake_client(
        monkeypatch,
        [_Resp(status_code=429, headers={"Retry-After": "1"}), _Resp(payload={"id": "evt_1"})],
    )
    result = await stripe_server._stripe_request(
        "POST", "/billing/meter_events", data={"event_name": "x"}, idempotency_key="key-1"
    )
    assert result == {"id": "evt_1"}
    assert len(calls) == 2
    assert calls[0]["headers"]["Idempotency-Key"] == "key-1"


async def test_keyless_post_network_error_not_retried(monkeypatch):
    calls = _install_fake_client(monkeypatch, [httpx.ConnectError("boom"), _Resp(payload={})])
    with pytest.raises(httpx.ConnectError):
        await stripe_server._stripe_request("POST", "/customers", data={"email": "a@b.com"})
    assert len(calls) == 1


# ── a representative tool end-to-end ─────────────────────────────────────────

async def test_ensure_customer_profile_creates_when_absent(monkeypatch):
    calls = _install_fake_client(
        monkeypatch,
        [
            _Resp(payload={"data": []}),               # GET /customers (none found)
            _Resp(payload={"id": "cus_new"}),          # POST /customers (create)
        ],
    )
    result = await stripe_server.ensure_customer_profile(
        email="jane@acme.com", first_name="Jane", last_name="Doe"
    )
    assert result["created"] is True
    assert result["stripe_customer_id"] == "cus_new"
    assert calls[1]["method"] == "POST"
    assert calls[1]["url"].endswith("/customers")
