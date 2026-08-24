"""Shared rate-limit-aware retry/backoff for outbound HTTP calls.

Used by the Outscraper and Stripe sub-servers. Retries only safe/transient
failures, honours an upstream ``Retry-After`` header, and uses capped
exponential backoff with full jitter so a fleet of clients does not
synchronise its retries (thundering herd).

Non-idempotent operations must opt in explicitly via ``retry_on_status``/the
caller's own gating — this module never decides idempotency for you.
"""
from __future__ import annotations

import asyncio
import email.utils
import random
from typing import Awaitable, Callable, Iterable

import httpx

# Transient HTTP statuses that are safe to retry when the operation is idempotent.
#   429 Too Many Requests  -> rate limited
#   500/502/503/504        -> transient upstream / gateway errors
DEFAULT_RETRY_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

DEFAULT_MAX_RETRIES = 4
DEFAULT_BASE_DELAY = 0.5
DEFAULT_MAX_DELAY = 20.0


def parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header (delta-seconds or HTTP-date) into seconds."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # delta-seconds form
    try:
        seconds = float(value)
        return max(0.0, seconds)
    except ValueError:
        pass
    # HTTP-date form
    parsed = email.utils.parsedate_to_datetime(value)
    if parsed is None:
        return None
    import datetime as _dt

    now = _dt.datetime.now(parsed.tzinfo or _dt.timezone.utc)
    delta = (parsed - now).total_seconds()
    return max(0.0, delta)


def _backoff_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Capped exponential backoff with full jitter. ``attempt`` is 0-indexed."""
    ceiling = min(max_delay, base_delay * (2 ** attempt))
    return random.uniform(0.0, ceiling)


async def request_with_retries(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retry_on_status: Iterable[int] = DEFAULT_RETRY_STATUSES,
    retry_network_errors: bool = True,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> httpx.Response:
    """Execute ``send`` with retry/backoff, returning the final ``httpx.Response``.

    ``send`` must build and issue a single request each time it is awaited
    (build the client inside so retries get a fresh connection). Only transient
    failures are retried; the final response — success or error — is returned to
    the caller so it can inspect/raise as it sees fit.

    The caller is responsible for ensuring ``send`` is safe to invoke more than
    once (i.e. the underlying operation is idempotent). Pass an empty
    ``retry_on_status`` and ``retry_network_errors=False`` to disable retries.
    """
    if sleep is None:
        sleep = asyncio.sleep
    retry_statuses = frozenset(retry_on_status)
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        is_last = attempt == max_retries
        try:
            response = await send()
        except httpx.RequestError as exc:  # network / timeout / connection errors
            last_exc = exc
            if not retry_network_errors or is_last:
                raise
            await sleep(_backoff_delay(attempt, base_delay, max_delay))
            continue

        if response.status_code in retry_statuses and not is_last:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            delay = retry_after if retry_after is not None else _backoff_delay(
                attempt, base_delay, max_delay
            )
            await sleep(delay)
            continue

        return response

    # Only reachable if the loop exhausted on network errors without re-raising.
    assert last_exc is not None
    raise last_exc
