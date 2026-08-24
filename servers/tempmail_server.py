"""
TempMail.so MCP Sub-Server (via RapidAPI)
Wraps the TempMail.so temporary-mailbox API (tempmail-so.p.rapidapi.com) as MCP tools.
This file is mounted into the main orchestrator — do NOT call mcp.run() here.

Purpose: give outreach campaigns disposable inboxes for signup verification,
deliverability/seed testing, and burner reply addresses — without leaking the
operator's real mailbox.

Tools:
- list_domains              → available sending domains for the account tier
- create_mailbox            → create one temporary inbox
- create_campaign_mailboxes → bulk-create inboxes for a campaign
- list_mailboxes            → all inboxes on the account
- delete_mailbox            → tear down an inbox
- list_mails                → messages in an inbox
- read_mail                 → full message body
- delete_mail               → remove a message
- wait_for_mail             → poll an inbox until a message arrives
- extract_verification_code → pull an OTP/confirmation link out of a message

Credentials (two distinct values — they are NOT the same):
- RapidAPI key      → header 'x-rapidapi-key'   / env TEMPMAIL_RAPIDAPI_KEY
- TempMail.so token → header 'Authorization'    / env TEMPMAIL_AUTH_TOKEN
  Obtain the token at https://tempmail.so/mailboxes → Account → Account Information.
"""
from __future__ import annotations

import asyncio
import os
import re
import secrets
from typing import Any, Optional

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from servers.http_retry import request_with_retries

mcp = FastMCP(name="TempMail")

BASE_URL = "https://tempmail-so.p.rapidapi.com"
RAPIDAPI_HOST = "tempmail-so.p.rapidapi.com"

_HTTP_TIMEOUT = 30.0

# Lifespans accepted by POST /inboxes. 0 == persistent inbox (no auto-expiry).
VALID_LIFESPANS = (0, 300, 600, 900, 1200, 1800)

# Verified empirically against the live API: a 5-character prefix is rejected
# with the misleading "Missing Parameters" (code 513); 6 characters succeeds.
NAME_MIN_LENGTH = 6
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


# ── Credentials ────────────────────────────────────────────────────────────────

def _resolve_rapidapi_key() -> str:
    """Resolve the RapidAPI key for the current request.

    Precedence:
      1) inbound 'x-tempmail-rapidapi-key' header (per-tenant, multi-tenant safe)
      2) TEMPMAIL_RAPIDAPI_KEY environment variable (server default)

    A dedicated header name is used rather than the generic 'x-api-key' so a
    client can talk to Outscraper and TempMail in the same session without the
    two keys colliding. Never logged or persisted.
    """
    header_key = get_http_headers(include={"x-tempmail-rapidapi-key"}).get(
        "x-tempmail-rapidapi-key"
    )
    if header_key and header_key.strip():
        return header_key.strip()

    env_key = os.getenv("TEMPMAIL_RAPIDAPI_KEY", "")
    if env_key and env_key.strip():
        return env_key.strip()

    raise RuntimeError(
        "Missing TempMail RapidAPI key. Send it as the 'x-tempmail-rapidapi-key' "
        "request header from your MCP client, or set the TEMPMAIL_RAPIDAPI_KEY "
        "environment variable."
    )


def _resolve_auth_token() -> str:
    """Resolve the TempMail.so account bearer token for the current request.

    This is a SEPARATE credential from the RapidAPI key. Requests carrying only
    the RapidAPI key are rejected upstream with HTTP 403 'Invalid Login
    Credential' (code 257).

    Precedence:
      1) inbound 'x-tempmail-token' header (per-tenant)
      2) TEMPMAIL_AUTH_TOKEN environment variable (server default)
    """
    header_token = get_http_headers(include={"x-tempmail-token"}).get("x-tempmail-token")
    if header_token and header_token.strip():
        return header_token.strip().removeprefix("Bearer ").strip()

    env_token = os.getenv("TEMPMAIL_AUTH_TOKEN", "")
    if env_token and env_token.strip():
        return env_token.strip().removeprefix("Bearer ").strip()

    raise RuntimeError(
        "Missing TempMail.so account token. This is a different value from the "
        "RapidAPI key: get it at https://tempmail.so/mailboxes → Account → "
        "Account Information. Send it as the 'x-tempmail-token' request header, "
        "or set the TEMPMAIL_AUTH_TOKEN environment variable."
    )


def _headers(content_type: Optional[str] = None) -> dict:
    headers = {
        "x-rapidapi-key": _resolve_rapidapi_key(),
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Authorization": f"Bearer {_resolve_auth_token()}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


# ── Transport ──────────────────────────────────────────────────────────────────

def _unwrap(response: httpx.Response) -> dict:
    """Normalise a TempMail.so response into a plain dict.

    Upstream wraps payloads as {"message": ..., "data": ..., "code": ...} and
    signals auth failures with HTTP 403 + code 257. Those are surfaced as a
    clear error rather than an opaque status so the agent can tell the user
    which of the two credentials is wrong.
    """
    try:
        body: Any = response.json()
    except ValueError:
        body = {"raw": response.text}

    if response.status_code >= 400:
        message = ""
        if isinstance(body, dict):
            message = str(body.get("message", "")).strip()
        code = body.get("code") if isinstance(body, dict) else None

        if response.status_code in (401, 403):
            raise RuntimeError(
                f"TempMail.so rejected the credentials (HTTP {response.status_code}: "
                f"{message or 'unauthorized'}). Verify BOTH the RapidAPI key and the "
                "separate TempMail.so account bearer token."
            )
        # 796 = duplicate address on that domain. Actionable, not a server fault.
        if code == 796:
            raise RuntimeError(
                "That mailbox already exists on this domain. Pick a different name, "
                "or call list_mailboxes to reuse the existing inbox."
            )
        # 513 is returned for a too-short prefix as well as genuinely absent
        # fields, so the raw "Missing Parameters" text is misleading on its own.
        if code == 513:
            raise RuntimeError(
                "TempMail.so rejected the request parameters. Check that 'name' is at "
                f"least {NAME_MIN_LENGTH} characters and 'domain' came from list_domains "
                f"(upstream said: {message or 'Missing Parameters'})."
            )
        # Upstream returns a bodyless 500 when a prefix was previously used and
        # deleted on that domain; the name stays tombstoned and cannot be reused.
        if response.status_code >= 500:
            raise RuntimeError(
                f"TempMail.so returned HTTP {response.status_code}"
                f"{f' ({message})' if message else ' with an empty body'}. "
                "This is often a previously-deleted mailbox name being reused on the "
                "same domain — try a different name or another domain. Otherwise it is "
                "a transient upstream fault; retry shortly."
            )
        raise RuntimeError(
            f"TempMail.so request failed (HTTP {response.status_code}): "
            f"{message or response.text[:200]}"
        )

    if isinstance(body, dict):
        return body
    return {"data": body}


async def _request(
    method: str,
    endpoint: str,
    *,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    idempotent: bool = True,
) -> dict:
    content_type = "application/x-www-form-urlencoded" if data is not None else None
    headers = _headers(content_type)

    async def _send() -> httpx.Response:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            return await client.request(
                method,
                f"{BASE_URL}{endpoint}",
                headers=headers,
                params=params,
                data=data,
            )

    # Only replay requests that are safe to repeat. Inbox/mail creation is not
    # idempotent upstream, so a retry could silently create duplicates.
    if idempotent:
        response = await request_with_retries(_send)
    else:
        response = await _send()
    return _unwrap(response)


def _extract_inbox_id(payload: dict) -> Optional[str]:
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("id", "inbox_id", "inboxId", "_id"):
            value = data.get(key)
            if value:
                return str(value)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# MAILBOXES
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_domains() -> dict:
    """
    List the temporary-email domains available to your TempMail.so account.

    Call this before create_mailbox — the 'domain' argument must be one of these
    values. Free tiers expose a small set; paid tiers expose more.
    """
    return await _request("GET", "/domains")


async def _create_mailbox(name: str, domain: str, lifespan: int) -> dict:
    """Shared inbox-creation implementation.

    Kept separate from the tool function so ``create_campaign_mailboxes`` can
    reuse it directly. Decorated tools are not reliably callable as plain
    functions across FastMCP versions, so bulk creation must not go through the
    decorated ``create_mailbox``.
    """
    if lifespan not in VALID_LIFESPANS:
        raise ValueError(
            f"lifespan must be one of {VALID_LIFESPANS} (0 = no auto-expiry); got {lifespan}"
        )

    normalized = (name or "").strip().lower()
    if len(normalized) < NAME_MIN_LENGTH:
        raise ValueError(
            f"name must be at least {NAME_MIN_LENGTH} characters "
            f"(TempMail.so rejects shorter prefixes); got {normalized!r}"
        )
    if not NAME_PATTERN.match(normalized):
        raise ValueError(
            "name must start with a letter or digit and contain only letters, "
            f"digits, dots, underscores, or hyphens; got {normalized!r}"
        )
    name = normalized

    payload = await _request(
        "POST",
        "/inboxes",
        data={"name": name, "domain": domain, "lifespan": str(lifespan)},
        idempotent=False,
    )
    payload["email"] = f"{name}@{domain}"
    inbox_id = _extract_inbox_id(payload)
    if inbox_id:
        payload["inbox_id"] = inbox_id
    return payload


@mcp.tool()
async def create_mailbox(
    name: str,
    domain: str,
    lifespan: int = 0,
) -> dict:
    """
    Create a temporary email inbox for an outreach campaign.

    Use for signup verifications, deliverability seed tests, or burner reply
    addresses. The resulting address is "{name}@{domain}".

    Args:
        name: Email prefix, e.g. acme-outreach-01 (letters, digits, dashes)
        domain: A domain returned by list_domains
        lifespan: Seconds before auto-expiry — one of 0, 300, 600, 900, 1200, 1800.
                  0 means a long-lived inbox that does not auto-expire (default).
    """
    return await _create_mailbox(name=name, domain=domain, lifespan=lifespan)


@mcp.tool()
async def create_campaign_mailboxes(
    prefix: str,
    domain: str,
    count: int = 5,
    lifespan: int = 0,
    start_index: int = 1,
    unique_suffix: bool = False,
) -> dict:
    """
    Bulk-create numbered temporary inboxes for one outreach campaign.

    Creates '{prefix}-{n}@{domain}' for n in start_index..start_index+count-1.
    Inboxes are created sequentially to stay inside RapidAPI rate limits, and a
    failure on one inbox does not abort the rest — check 'failed' in the result.

    Note: TempMail.so will not reuse a prefix that already exists on a domain,
    and a prefix that was previously created and deleted stays unavailable on
    that domain. Set unique_suffix=True when re-running a campaign with the same
    prefix, or vary the prefix/domain.

    Args:
        prefix: Campaign slug, e.g. 'acme-q3' (result must be 6+ characters)
        domain: A domain returned by list_domains
        count: How many inboxes to create, 1–50 (default 5)
        lifespan: Seconds before auto-expiry — 0, 300, 600, 900, 1200, or 1800
        start_index: First numeric suffix (default 1) — resume a partial batch
        unique_suffix: Append a short random token to each name so a re-run of
                       the same campaign does not collide (default False)
    """
    if not 1 <= count <= 50:
        raise ValueError(f"count must be between 1 and 50; got {count}")
    if lifespan not in VALID_LIFESPANS:
        raise ValueError(
            f"lifespan must be one of {VALID_LIFESPANS} (0 = no auto-expiry); got {lifespan}"
        )

    batch_token = secrets.token_hex(2) if unique_suffix else ""

    created: list[dict] = []
    failed: list[dict] = []
    for offset in range(count):
        index = start_index + offset
        name = f"{prefix}-{index}-{batch_token}" if batch_token else f"{prefix}-{index}"
        try:
            result = await _create_mailbox(name=name, domain=domain, lifespan=lifespan)
            created.append(
                {
                    "email": result.get("email"),
                    "inbox_id": result.get("inbox_id"),
                    "index": index,
                }
            )
        except Exception as exc:  # noqa: BLE001 — surface per-inbox failure, keep going
            failed.append({"name": name, "index": index, "error": str(exc)})
        if offset < count - 1:
            await asyncio.sleep(0.4)

    return {
        "campaign_prefix": prefix,
        "batch_token": batch_token or None,
        "domain": domain,
        "requested": count,
        "created_count": len(created),
        "created": created,
        "failed": failed,
    }


@mcp.tool()
async def list_mailboxes() -> dict:
    """
    List every temporary inbox on your TempMail.so account, with IDs and addresses.

    Use this to recover inbox IDs for a campaign created in an earlier session.
    """
    return await _request("GET", "/inboxes")


@mcp.tool()
async def delete_mailbox(inbox_id: str) -> dict:
    """
    Permanently delete a temporary inbox and its messages.

    Args:
        inbox_id: Inbox ID from create_mailbox or list_mailboxes
    """
    return await _request("DELETE", f"/inboxes/{inbox_id}", idempotent=False)


# ══════════════════════════════════════════════════════════════════════════════
# MAIL
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_mails(inbox_id: str) -> dict:
    """
    List all messages received by a temporary inbox (subject, sender, timestamp).

    Args:
        inbox_id: Inbox ID from create_mailbox or list_mailboxes
    """
    return await _request("GET", f"/inboxes/{inbox_id}/mails")


@mcp.tool()
async def read_mail(inbox_id: str, mail_id: str) -> dict:
    """
    Read the full content of one message — subject, sender, headers, and body.

    Args:
        inbox_id: Inbox ID from create_mailbox or list_mailboxes
        mail_id: Message ID from list_mails
    """
    return await _request("GET", f"/inboxes/{inbox_id}/mails/{mail_id}")


@mcp.tool()
async def delete_mail(inbox_id: str, mail_id: str) -> dict:
    """
    Delete a single message from a temporary inbox.

    Args:
        inbox_id: Inbox ID from create_mailbox or list_mailboxes
        mail_id: Message ID from list_mails
    """
    return await _request(
        "DELETE", f"/inboxes/{inbox_id}/mails/{mail_id}", idempotent=False
    )


@mcp.tool()
async def wait_for_mail(
    inbox_id: str,
    timeout_seconds: int = 60,
    poll_interval_seconds: int = 5,
    from_contains: Optional[str] = None,
    subject_contains: Optional[str] = None,
) -> dict:
    """
    Poll an inbox until a matching message arrives or the timeout elapses.

    Avoids the agent hand-rolling a retry loop when waiting on a signup
    confirmation or verification email.

    Args:
        inbox_id: Inbox ID from create_mailbox or list_mailboxes
        timeout_seconds: Give up after this long, 5–300 (default 60)
        poll_interval_seconds: Seconds between checks, 2–30 (default 5)
        from_contains: Only match if the sender contains this text (case-insensitive)
        subject_contains: Only match if the subject contains this text (case-insensitive)
    """
    if not 5 <= timeout_seconds <= 300:
        raise ValueError(f"timeout_seconds must be between 5 and 300; got {timeout_seconds}")
    if not 2 <= poll_interval_seconds <= 30:
        raise ValueError(
            f"poll_interval_seconds must be between 2 and 30; got {poll_interval_seconds}"
        )

    def _matches(mail: dict) -> bool:
        if from_contains:
            sender = str(mail.get("from") or mail.get("sender") or "")
            if from_contains.lower() not in sender.lower():
                return False
        if subject_contains:
            subject = str(mail.get("subject") or "")
            if subject_contains.lower() not in subject.lower():
                return False
        return True

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    polls = 0

    while True:
        polls += 1
        payload = await _request("GET", f"/inboxes/{inbox_id}/mails")
        data = payload.get("data")
        mails = data if isinstance(data, list) else (data or {}).get("mails", []) if isinstance(data, dict) else []
        matching = [m for m in mails if isinstance(m, dict) and _matches(m)]
        if matching:
            return {
                "found": True,
                "polls": polls,
                "match_count": len(matching),
                "mails": matching,
            }
        if loop.time() + poll_interval_seconds >= deadline:
            return {
                "found": False,
                "polls": polls,
                "timeout_seconds": timeout_seconds,
                "message": "No matching mail arrived before the timeout.",
            }
        await asyncio.sleep(poll_interval_seconds)


@mcp.tool()
async def extract_verification_code(inbox_id: str, mail_id: str) -> dict:
    """
    Pull verification codes and confirmation links out of a message.

    Returns numeric/alphanumeric OTP candidates plus any http(s) links found in
    the body, so the agent can complete a signup without parsing raw HTML.

    Args:
        inbox_id: Inbox ID from create_mailbox or list_mailboxes
        mail_id: Message ID from list_mails
    """
    payload = await _request("GET", f"/inboxes/{inbox_id}/mails/{mail_id}")
    data = payload.get("data")
    source = data if isinstance(data, dict) else payload

    # TempMail.so returns bodies as "textContent" / "htmlContent". The remaining
    # keys are defensive fallbacks in case the upstream schema shifts.
    body_parts = [
        str(source.get(key, ""))
        for key in (
            "subject",
            "textContent",
            "htmlContent",
            "text",
            "textBody",
            "body",
            "html",
            "htmlBody",
            "content",
        )
    ]
    body = "\n".join(part for part in body_parts if part)
    # Strip tags so codes inside HTML markup are not fused to attribute text.
    plain = re.sub(r"<[^>]+>", " ", body)

    codes = re.findall(r"\b(?=[A-Z0-9-]*\d)[A-Z0-9]{4,8}\b", plain.upper())
    links = re.findall(r"https?://[^\s\"'<>\)]+", body)

    seen: set[str] = set()
    unique_codes = [c for c in codes if not (c in seen or seen.add(c))]
    seen_links: set[str] = set()
    unique_links = [l for l in links if not (l in seen_links or seen_links.add(l))]

    return {
        "inbox_id": inbox_id,
        "mail_id": mail_id,
        "subject": source.get("subject"),
        "from": source.get("from") or source.get("sender"),
        "code_candidates": unique_codes[:10],
        "links": unique_links[:10],
    }
