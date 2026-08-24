"""Chained-workflow test across Stripe billing tools.

Mirrors the "search customer -> fetch entitlement -> record billable usage"
shape requested for end-to-end coverage. The codebase's billing surface is
subscription/metered-usage based (there is no payment-intent/refund tool), so
the representative chain exercised here is:

    ensure_customer_profile        (find-or-create the customer)
        -> get_customer_export_access   (fetch entitlement / subscription state)
        -> record_qualified_lead_export (post the billable meter event)

All Stripe HTTP is mocked; each step feeds the next.
"""
import httpx
import pytest

from servers import http_retry, stripe_server


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = {}
        self.text = ""

    @property
    def is_error(self):
        return self.status_code >= 400

    def json(self):
        return self._payload


def _router(monkeypatch, handler):
    """Install a fake client that dispatches each request through ``handler``."""
    calls: list[dict] = []

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, auth=None, data=None, params=None, headers=None):
            record = {"method": method, "url": url, "data": data, "params": params}
            calls.append(record)
            return handler(record)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    return calls


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    async def _s(_):
        return None

    monkeypatch.setattr(http_retry.asyncio, "sleep", _s)
    monkeypatch.setattr(http_retry.random, "uniform", lambda lo, hi: 0.0)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_chain")
    monkeypatch.setenv("BILLING_CONSENT_MODE", "per_batch")
    monkeypatch.setenv("BILLING_REQUIRE_EXPORT_BATCH_ID", "true")
    monkeypatch.setenv("STRIPE_ENFORCE_EXPORT_ACCESS_CHECK", "true")
    # Isolate the in-process idempotency ledger between tests.
    stripe_server._EXPORT_BILLING_LEDGER.clear()


async def test_customer_to_access_to_usage_chain(monkeypatch):
    customer_id = "cus_chain_1"

    def handler(rec):
        url, method = rec["url"], rec["method"]
        if url.endswith("/customers") and method == "GET":
            return _Resp(payload={"data": []})            # step 1a: not found
        if url.endswith("/customers") and method == "POST":
            return _Resp(payload={"id": customer_id})     # step 1b: created
        if url.endswith("/subscriptions") and method == "GET":
            return _Resp(payload={"data": [               # step 2: active access
                {"status": "active", "items": {"data": []}}
            ]})
        if url.endswith("/billing/meter_events") and method == "POST":
            return _Resp(payload={"identifier": "mev_1"}) # step 3: metered
        raise AssertionError(f"unexpected call: {method} {url}")

    calls = _router(monkeypatch, handler)

    # Step 1: find-or-create the customer.
    profile = await stripe_server.ensure_customer_profile(
        email="lead@acme.com", first_name="Sam", last_name="Rivera"
    )
    assert profile["stripe_customer_id"] == customer_id

    # Step 2: confirm the customer is entitled to export.
    access = await stripe_server.get_customer_export_access(
        stripe_customer_id=profile["stripe_customer_id"]
    )
    assert access["has_export_access"] is True

    # Step 3: record the billable usage (consent + batch id supplied).
    usage = await stripe_server.record_qualified_lead_export(
        stripe_customer_id=profile["stripe_customer_id"],
        leads_exported=3,
        export_batch_id="batch-xyz",
        consent_granted=True,
    )
    assert usage["meter_event_id"] == "mev_1"
    assert usage["qualified_leads"] == 3
    assert usage["already_recorded"] is False

    methods = [(c["method"], c["url"].rsplit("/", 1)[-1]) for c in calls]
    assert ("POST", "meter_events") in methods


async def test_chain_blocks_usage_without_consent(monkeypatch):
    def handler(rec):
        if rec["url"].endswith("/subscriptions"):
            return _Resp(payload={"data": [{"status": "active", "items": {"data": []}}]})
        raise AssertionError(f"should not reach: {rec['method']} {rec['url']}")

    _router(monkeypatch, handler)
    with pytest.raises(ValueError, match="permission is required"):
        await stripe_server.record_qualified_lead_export(
            stripe_customer_id="cus_x",
            leads_exported=1,
            export_batch_id="b1",
            consent_granted=False,
        )


async def test_chain_is_idempotent_on_repeat_batch(monkeypatch):
    def handler(rec):
        if rec["url"].endswith("/subscriptions"):
            return _Resp(payload={"data": [{"status": "active", "items": {"data": []}}]})
        if rec["url"].endswith("/billing/meter_events"):
            return _Resp(payload={"identifier": "mev_dup"})
        raise AssertionError(f"unexpected: {rec['method']} {rec['url']}")

    _router(monkeypatch, handler)
    kwargs = dict(
        stripe_customer_id="cus_dup",
        leads_exported=2,
        export_batch_id="same-batch",
        consent_granted=True,
    )
    first = await stripe_server.record_qualified_lead_export(**kwargs)
    second = await stripe_server.record_qualified_lead_export(**kwargs)
    assert first["already_recorded"] is False
    assert second["already_recorded"] is True
