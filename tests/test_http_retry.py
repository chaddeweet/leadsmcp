"""Tests for the shared rate-limit-aware retry/backoff helper."""
import httpx
import pytest

from servers import http_retry
from servers.http_retry import parse_retry_after, request_with_retries


class _Resp:
    def __init__(self, status_code: int, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Neutralise jitter and record sleep durations instead of waiting."""
    slept: list[float] = []

    async def _fake_sleep(seconds: float):
        slept.append(seconds)

    monkeypatch.setattr(http_retry.asyncio, "sleep", _fake_sleep)
    # Deterministic jitter: full-jitter uniform(0, ceiling) -> ceiling.
    monkeypatch.setattr(http_retry.random, "uniform", lambda lo, hi: hi)
    return slept


def _sender(responses):
    calls = {"n": 0}
    seq = list(responses)

    async def _send():
        idx = calls["n"]
        calls["n"] += 1
        item = seq[idx]
        if isinstance(item, Exception):
            raise item
        return item

    return _send, calls


# ── Retry-After parsing ───────────────────────────────────────────────────────

def test_parse_retry_after_seconds():
    assert parse_retry_after("5") == 5.0


def test_parse_retry_after_blank_or_none():
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None


def test_parse_retry_after_http_date_is_non_negative():
    # A past date should clamp to 0, never negative.
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0


# ── Retry behaviour ───────────────────────────────────────────────────────────

async def test_retries_on_429_then_succeeds(_no_real_sleep):
    send, calls = _sender([_Resp(429), _Resp(200)])
    resp = await request_with_retries(send, base_delay=1.0, max_delay=10.0)
    assert resp.status_code == 200
    assert calls["n"] == 2
    assert len(_no_real_sleep) == 1


async def test_honours_retry_after_header(_no_real_sleep):
    send, _ = _sender([_Resp(429, {"Retry-After": "7"}), _Resp(200)])
    await request_with_retries(send, base_delay=1.0)
    assert _no_real_sleep == [7.0]


async def test_retries_on_5xx(_no_real_sleep):
    send, calls = _sender([_Resp(503), _Resp(502), _Resp(200)])
    resp = await request_with_retries(send)
    assert resp.status_code == 200
    assert calls["n"] == 3


async def test_gives_up_after_max_retries_returns_last(_no_real_sleep):
    send, calls = _sender([_Resp(429)] * 10)
    resp = await request_with_retries(send, max_retries=2)
    assert resp.status_code == 429
    # 1 initial + 2 retries = 3 calls; 2 sleeps.
    assert calls["n"] == 3
    assert len(_no_real_sleep) == 2


async def test_no_retry_on_4xx_client_error(_no_real_sleep):
    send, calls = _sender([_Resp(400), _Resp(200)])
    resp = await request_with_retries(send)
    assert resp.status_code == 400
    assert calls["n"] == 1
    assert _no_real_sleep == []


async def test_network_error_retried_then_succeeds(_no_real_sleep):
    send, calls = _sender([httpx.ConnectError("boom"), _Resp(200)])
    resp = await request_with_retries(send)
    assert resp.status_code == 200
    assert calls["n"] == 2


async def test_network_errors_can_be_disabled(_no_real_sleep):
    send, calls = _sender([httpx.ConnectError("boom"), _Resp(200)])
    with pytest.raises(httpx.ConnectError):
        await request_with_retries(send, retry_network_errors=False)
    assert calls["n"] == 1


async def test_zero_max_retries_disables_retry(_no_real_sleep):
    send, calls = _sender([_Resp(429), _Resp(200)])
    resp = await request_with_retries(send, max_retries=0)
    assert resp.status_code == 429
    assert calls["n"] == 1
