"""Tests for the TempMail.so sub-server.

Payload fixtures mirror the shapes documented at
https://tempmail.so/blog/how-to-use-the-temporary-email-service-api
(notably ``textContent`` / ``htmlContent`` for mail bodies, and ``data: {}``
rather than an empty list for an inbox with no mail).
"""
import asyncio

import pytest

from servers import tempmail_server as tm


_REAL_SLEEP = asyncio.sleep


def _no_sleep(monkeypatch):
    """Skip real delays without recursing into the patched sleep."""
    async def instant(_seconds):
        await _REAL_SLEEP(0)

    monkeypatch.setattr(tm.asyncio, "sleep", instant)


# ── Fixtures mirroring real upstream payloads ─────────────────────────────────

MAIL_LIST_POPULATED = {
    "request-id": "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
    "message": "Success",
    "code": 0,
    "data": [
        {
            "received": 1700000000,
            "from": "noreply@acme.com",
            "read": False,
            "id": "MAIL-1",
            "subject": "Verify your Acme account",
        },
        {
            "received": 1700000100,
            "from": "hello@other.com",
            "read": False,
            "id": "MAIL-2",
            "subject": "Newsletter",
        },
    ],
}

MAIL_LIST_EMPTY = {"request-id": "x", "message": "Success", "code": 0, "data": {}}

MAIL_DETAIL = {
    "request-id": "x",
    "message": "Success",
    "code": 0,
    "data": {
        "textContent": "Your verification code is 483920",
        "forwarded": False,
        "htmlContent": (
            "<html><body><h1>Welcome</h1>"
            "<p>Your code is <b>483920</b></p>"
            "<a href='https://acme.com/confirm?token=abc123'>Confirm</a>"
            "</body></html>"
        ),
        "received": 1700000000,
        "from": "noreply@acme.com",
        "read": False,
        "id": "MAIL-1",
        "subject": "Verify your Acme account",
    },
}


@pytest.fixture(autouse=True)
def _creds(monkeypatch):
    monkeypatch.setenv("TEMPMAIL_RAPIDAPI_KEY", "test-key")
    monkeypatch.setenv("TEMPMAIL_AUTH_TOKEN", "test-token")


def _stub_request(monkeypatch, payload):
    calls = []

    async def fake(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return payload() if callable(payload) else payload

    monkeypatch.setattr(tm, "_request", fake)
    return calls


# ── Credential resolution ─────────────────────────────────────────────────────

def test_missing_rapidapi_key_raises_actionable_error(monkeypatch):
    monkeypatch.delenv("TEMPMAIL_RAPIDAPI_KEY", raising=False)
    with pytest.raises(RuntimeError, match="x-tempmail-rapidapi-key"):
        tm._resolve_rapidapi_key()


def test_missing_account_token_distinguishes_from_rapidapi_key(monkeypatch):
    monkeypatch.delenv("TEMPMAIL_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="different value from the RapidAPI key"):
        tm._resolve_auth_token()


def test_token_bearer_prefix_is_stripped(monkeypatch):
    monkeypatch.setenv("TEMPMAIL_AUTH_TOKEN", "Bearer abc-123")
    assert tm._resolve_auth_token() == "abc-123"


def test_headers_carry_both_credentials():
    headers = tm._headers()
    assert headers["x-rapidapi-key"] == "test-key"
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["x-rapidapi-host"] == tm.RAPIDAPI_HOST


# ── Input validation ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("lifespan", [1, 77, 3600, -1])
def test_create_mailbox_rejects_invalid_lifespan(lifespan):
    with pytest.raises(ValueError, match="lifespan must be one of"):
        asyncio.run(tm._create_mailbox(name="mailbox", domain="d.com", lifespan=lifespan))


@pytest.mark.parametrize("lifespan", list(tm.VALID_LIFESPANS))
def test_create_mailbox_accepts_documented_lifespans(monkeypatch, lifespan):
    _stub_request(monkeypatch, {"code": 0, "data": {"id": "INBOX-1"}})
    result = asyncio.run(tm._create_mailbox(name="mailbox", domain="d.com", lifespan=lifespan))
    assert result["inbox_id"] == "INBOX-1"
    assert result["email"] == "mailbox@d.com"


@pytest.mark.parametrize("count", [0, 51, 999])
def test_campaign_rejects_out_of_range_count(count):
    with pytest.raises(ValueError, match="count must be between"):
        asyncio.run(tm.create_campaign_mailboxes(prefix="camp", domain="d.com", count=count))


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"timeout_seconds": 1}, "timeout_seconds"),
        ({"timeout_seconds": 9999}, "timeout_seconds"),
        ({"poll_interval_seconds": 1}, "poll_interval_seconds"),
        ({"poll_interval_seconds": 99}, "poll_interval_seconds"),
    ],
)
def test_wait_for_mail_validates_bounds(kwargs, match):
    with pytest.raises(ValueError, match=match):
        asyncio.run(tm.wait_for_mail(inbox_id="i", **kwargs))


# ── Bulk creation ─────────────────────────────────────────────────────────────

def test_campaign_creates_sequential_names(monkeypatch):
    _no_sleep(monkeypatch)
    _stub_request(monkeypatch, lambda: {"code": 0, "data": {"id": "INBOX-X"}})
    result = asyncio.run(
        tm.create_campaign_mailboxes(prefix="acme", domain="d.com", count=3, start_index=5)
    )
    assert result["created_count"] == 3
    assert [c["email"] for c in result["created"]] == [
        "acme-5@d.com",
        "acme-6@d.com",
        "acme-7@d.com",
    ]
    assert result["failed"] == []


def test_campaign_survives_partial_failure(monkeypatch):
    _no_sleep(monkeypatch)
    state = {"n": 0}

    async def flaky(method, endpoint, **kwargs):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("upstream rate limit")
        return {"code": 0, "data": {"id": f"INBOX-{state['n']}"}}

    monkeypatch.setattr(tm, "_request", flaky)
    result = asyncio.run(tm.create_campaign_mailboxes(prefix="camp", domain="d.com", count=3))
    assert result["created_count"] == 2
    assert len(result["failed"]) == 1
    assert "rate limit" in result["failed"][0]["error"]


# ── wait_for_mail against real payload shapes ─────────────────────────────────

def test_wait_for_mail_handles_empty_inbox_dict(monkeypatch):
    """An inbox with no mail returns ``data: {}``, not an empty list."""
    _no_sleep(monkeypatch)
    _stub_request(monkeypatch, MAIL_LIST_EMPTY)
    result = asyncio.run(
        tm.wait_for_mail(inbox_id="i", timeout_seconds=5, poll_interval_seconds=5)
    )
    assert result["found"] is False


def test_wait_for_mail_finds_message(monkeypatch):
    _stub_request(monkeypatch, MAIL_LIST_POPULATED)
    result = asyncio.run(
        tm.wait_for_mail(inbox_id="i", timeout_seconds=5, poll_interval_seconds=2)
    )
    assert result["found"] is True
    assert result["match_count"] == 2


def test_wait_for_mail_filters_by_sender_and_subject(monkeypatch):
    _stub_request(monkeypatch, MAIL_LIST_POPULATED)
    result = asyncio.run(
        tm.wait_for_mail(
            inbox_id="i",
            timeout_seconds=5,
            poll_interval_seconds=2,
            from_contains="ACME",  # case-insensitive
            subject_contains="verify",
        )
    )
    assert result["found"] is True
    assert result["match_count"] == 1
    assert result["mails"][0]["id"] == "MAIL-1"


def test_wait_for_mail_non_matching_filter_times_out(monkeypatch):
    _no_sleep(monkeypatch)
    _stub_request(monkeypatch, MAIL_LIST_POPULATED)
    result = asyncio.run(
        tm.wait_for_mail(
            inbox_id="i",
            timeout_seconds=5,
            poll_interval_seconds=5,
            from_contains="nobody@nowhere.test",
        )
    )
    assert result["found"] is False


# ── Verification-code extraction ──────────────────────────────────────────────

def test_extract_reads_textcontent_and_htmlcontent(monkeypatch):
    """Regression: bodies live in textContent/htmlContent, not text/body/html."""
    _stub_request(monkeypatch, MAIL_DETAIL)
    result = asyncio.run(tm.extract_verification_code(inbox_id="i", mail_id="MAIL-1"))
    assert "483920" in result["code_candidates"]
    assert "https://acme.com/confirm?token=abc123" in result["links"]
    assert result["subject"] == "Verify your Acme account"
    assert result["from"] == "noreply@acme.com"


def test_extract_strips_html_tags_so_codes_are_not_fused(monkeypatch):
    payload = {
        "code": 0,
        "data": {
            "subject": "Code",
            "textContent": "",
            "htmlContent": "<p>Code:</p><b>112233</b><span>445566</span>",
            "from": "a@b.com",
        },
    }
    _stub_request(monkeypatch, payload)
    result = asyncio.run(tm.extract_verification_code(inbox_id="i", mail_id="m"))
    assert "112233" in result["code_candidates"]
    assert "445566" in result["code_candidates"]


def test_extract_handles_message_with_no_code(monkeypatch):
    payload = {
        "code": 0,
        "data": {"subject": "Hello", "textContent": "Just saying hi.", "from": "a@b.com"},
    }
    _stub_request(monkeypatch, payload)
    result = asyncio.run(tm.extract_verification_code(inbox_id="i", mail_id="m"))
    assert result["code_candidates"] == []
    assert result["links"] == []


# ── Error surfacing ───────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_auth_failure_names_both_credentials():
    resp = _Resp(403, {"message": "Invalid Login Credential", "code": 257})
    with pytest.raises(RuntimeError, match="BOTH the RapidAPI key"):
        tm._unwrap(resp)


def test_generic_upstream_error_is_surfaced():
    resp = _Resp(500, {"message": "boom"})
    with pytest.raises(RuntimeError, match="boom"):
        tm._unwrap(resp)


def test_successful_response_passes_through():
    resp = _Resp(200, {"code": 0, "data": [{"domain": "x.com"}]})
    assert tm._unwrap(resp)["data"] == [{"domain": "x.com"}]


# ── Idempotency guard ─────────────────────────────────────────────────────────

def test_mutating_calls_do_not_retry(monkeypatch):
    """Retrying POST/DELETE could duplicate inboxes, so they must not replay."""
    seen = {}

    async def fake_send_capture(method, endpoint, *, params=None, data=None, idempotent=True):
        seen[(method, endpoint)] = idempotent
        return {"code": 0, "data": {"id": "X"}}

    monkeypatch.setattr(tm, "_request", fake_send_capture)
    asyncio.run(tm._create_mailbox(name="mailbox", domain="d.com", lifespan=0))
    asyncio.run(tm.delete_mailbox(inbox_id="i"))
    asyncio.run(tm.delete_mail(inbox_id="i", mail_id="m"))
    assert seen[("POST", "/inboxes")] is False
    assert seen[("DELETE", "/inboxes/i")] is False
    assert seen[("DELETE", "/inboxes/i/mails/m")] is False


def test_read_calls_are_retryable(monkeypatch):
    seen = {}

    async def fake(method, endpoint, *, params=None, data=None, idempotent=True):
        seen[(method, endpoint)] = idempotent
        return {"code": 0, "data": []}

    monkeypatch.setattr(tm, "_request", fake)
    asyncio.run(tm.list_domains())
    asyncio.run(tm.list_mailboxes())
    assert seen[("GET", "/domains")] is True
    assert seen[("GET", "/inboxes")] is True


# ── Name constraints (verified against the live API) ──────────────────────────

@pytest.mark.parametrize("name", ["a", "abc", "abcde"])
def test_name_shorter_than_minimum_rejected_locally(name):
    """Upstream returns a misleading 'Missing Parameters' for short prefixes."""
    with pytest.raises(ValueError, match="at least 6 characters"):
        asyncio.run(tm._create_mailbox(name=name, domain="d.com", lifespan=0))


@pytest.mark.parametrize("name", ["-leadingdash", "has space here", "bad!chars!!", "@nopenope"])
def test_invalid_name_characters_rejected(name):
    with pytest.raises(ValueError, match="name must start with"):
        asyncio.run(tm._create_mailbox(name=name, domain="d.com", lifespan=0))


def test_name_is_lowercased_and_trimmed(monkeypatch):
    calls = _stub_request(monkeypatch, {"code": 0, "data": {"id": "X"}})
    result = asyncio.run(tm._create_mailbox(name="  ACME-Outreach  ", domain="d.com", lifespan=0))
    assert calls[0][2]["data"]["name"] == "acme-outreach"
    assert result["email"] == "acme-outreach@d.com"


def test_duplicate_mailbox_error_is_actionable():
    resp = _Resp(400, {"message": "The Mailbox Already Exists", "code": 796})
    with pytest.raises(RuntimeError, match="already exists on this domain"):
        tm._unwrap(resp)


def test_missing_parameters_error_mentions_length_rule():
    resp = _Resp(400, {"message": "Missing Parameters", "code": 513})
    with pytest.raises(RuntimeError, match="at least 6 characters"):
        tm._unwrap(resp)


def test_bodyless_500_explains_tombstoned_name():
    resp = _Resp(500, {})
    with pytest.raises(RuntimeError, match="previously-deleted mailbox name"):
        tm._unwrap(resp)


def test_unique_suffix_makes_names_collision_resistant(monkeypatch):
    _no_sleep(monkeypatch)
    _stub_request(monkeypatch, lambda: {"code": 0, "data": {"id": "X"}})
    a = asyncio.run(
        tm.create_campaign_mailboxes(prefix="acme", domain="d.com", count=2, unique_suffix=True)
    )
    b = asyncio.run(
        tm.create_campaign_mailboxes(prefix="acme", domain="d.com", count=2, unique_suffix=True)
    )
    assert a["batch_token"] and b["batch_token"]
    assert a["batch_token"] != b["batch_token"]
    assert {c["email"] for c in a["created"]}.isdisjoint({c["email"] for c in b["created"]})


def test_without_unique_suffix_names_are_deterministic(monkeypatch):
    _no_sleep(monkeypatch)
    _stub_request(monkeypatch, lambda: {"code": 0, "data": {"id": "X"}})
    a = asyncio.run(tm.create_campaign_mailboxes(prefix="acme", domain="d.com", count=2))
    assert [c["email"] for c in a["created"]] == ["acme-1@d.com", "acme-2@d.com"]
    assert a["batch_token"] is None
