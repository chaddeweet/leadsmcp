"""
Stripe Billing MCP Sub-Server
Handles customer registration, subscription gating, export quoting, and usage meter events.

This module is intentionally strict about export charging:
- Free search/browse is allowed upstream.
- Billing occurs only when qualified leads are exported.
- Export charges can be guarded by explicit per-batch permission.
- Batch IDs are used to prevent accidental double billing.
"""

import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP

from servers.http_retry import request_with_retries

mcp = FastMCP(name="Stripe Billing")

STRIPE_API_BASE = "https://api.stripe.com/v1"
DEFAULT_STRIPE_API_VERSION = "2026-02-25.clover"
DEFAULT_METER_EVENT_NAME = "qualified_lead_export"
DEFAULT_METER_VALUE_FIELD = "leads_exported"
DEFAULT_METER_CUSTOMER_FIELD = "stripe_customer_id"
DEFAULT_QUALIFIED_LEAD_UNIT_PRICE_USD = 1.20
DEFAULT_BILLING_CONSENT_MODE = "per_batch"

_EXPORT_BILLING_LEDGER: dict[str, dict[str, Any]] = {}


def _required_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional_float(raw: str, fallback: float) -> float:
    try:
        parsed = float(raw.strip())
    except ValueError:
        return fallback
    if parsed <= 0:
        return fallback
    return parsed


def _billing_consent_mode() -> str:
    mode = os.getenv("BILLING_CONSENT_MODE", DEFAULT_BILLING_CONSENT_MODE).strip().lower()
    if mode not in {"per_batch", "auto"}:
        return DEFAULT_BILLING_CONSENT_MODE
    return mode


def _require_export_batch_id() -> bool:
    return _truthy(os.getenv("BILLING_REQUIRE_EXPORT_BATCH_ID", "true"))


def _enforce_export_access_check() -> bool:
    return _truthy(os.getenv("STRIPE_ENFORCE_EXPORT_ACCESS_CHECK", "true"))


def _qualified_lead_unit_price(default_override: float = 0.0) -> float:
    if default_override > 0:
        return round(default_override, 4)
    return round(
        _optional_float(
            os.getenv("QUALIFIED_LEAD_UNIT_PRICE_USD", str(DEFAULT_QUALIFIED_LEAD_UNIT_PRICE_USD)),
            DEFAULT_QUALIFIED_LEAD_UNIT_PRICE_USD,
        ),
        4,
    )


def _status_set(env_key: str, default_values: set[str]) -> set[str]:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return default_values
    parsed = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return parsed or default_values


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
    return ""


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "verified", "valid"}
    return False


def _first_non_empty(record: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        candidate = _coerce_text(record.get(key))
        if candidate:
            return candidate
    return ""


def _safe_full_name(full_name: str, first_name: str, last_name: str) -> str:
    if full_name.strip():
        return full_name.strip()
    return f"{first_name.strip()} {last_name.strip()}".strip()


def _normalize_customer_payload(
    *,
    email: str,
    first_name: str,
    last_name: str,
    phone: str,
    full_name: str,
) -> dict[str, str]:
    payload: dict[str, str] = {
        "email": email.strip(),
        "name": full_name,
        "metadata[source]": "leadsmcp",
        "metadata[first_name]": first_name.strip(),
        "metadata[last_name]": last_name.strip(),
        "metadata[full_name]": full_name,
    }
    if phone.strip():
        payload["phone"] = phone.strip()
        payload["metadata[phone]"] = phone.strip()
    return payload


def _stripe_headers(idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Stripe-Version": os.getenv("STRIPE_API_VERSION", DEFAULT_STRIPE_API_VERSION),
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _stripe_error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        err = payload.get("error", {})
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    return fallback


def _stripe_retry_allowed(method: str, idempotency_key: str | None) -> bool:
    """Decide whether a Stripe call is safe to retry after a transient failure.

    - GET/HEAD are read-only and always safe to repeat.
    - Writes (POST/DELETE) are only safe to retry when they carry an
      Idempotency-Key, which lets Stripe dedupe the repeat server-side. Retrying
      a keyless write could double-charge or create duplicate resources, so we
      refuse to retry those.
    """
    if method.upper() in {"GET", "HEAD"}:
        return True
    return bool(idempotency_key and idempotency_key.strip())


async def _stripe_request(
    method: str,
    path: str,
    *,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    secret = _required_env("STRIPE_SECRET_KEY")
    retryable = _stripe_retry_allowed(method, idempotency_key)

    async def _send() -> httpx.Response:
        async with httpx.AsyncClient(timeout=45.0) as client:
            return await client.request(
                method=method,
                url=f"{STRIPE_API_BASE}{path}",
                auth=(secret, ""),
                data=data,
                params=params,
                headers=_stripe_headers(idempotency_key=idempotency_key),
            )

    response = await request_with_retries(
        _send,
        max_retries=4 if retryable else 0,
        retry_network_errors=retryable,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.is_error:
        message = _stripe_error_message(payload, response.text)
        raise RuntimeError(f"Stripe API {response.status_code}: {message}")

    if not isinstance(payload, dict):
        raise RuntimeError("Stripe API returned a non-JSON object payload.")
    return payload


def _graduated_tier_breakdown(leads_exported: int) -> tuple[list[dict[str, Any]], float]:
    tiers = [
        (5, 0.99),
        (100, 2.00),
        (500, 1.50),
        (2000, 1.00),
        (None, 0.75),
    ]
    remaining = leads_exported
    prev_limit = 0
    total_cost = 0.0
    breakdown: list[dict[str, Any]] = []

    for upper_limit, unit_price in tiers:
        if remaining <= 0:
            break

        tier_capacity = remaining if upper_limit is None else min(remaining, upper_limit - prev_limit)
        if tier_capacity <= 0:
            if upper_limit is not None:
                prev_limit = upper_limit
            continue

        tier_cost = round(tier_capacity * unit_price, 2)
        total_cost += tier_cost
        tier_label = f"{prev_limit + 1}+" if upper_limit is None else f"{prev_limit + 1}-{upper_limit}"
        breakdown.append(
            {
                "tier": tier_label,
                "units": tier_capacity,
                "unit_price_usd": unit_price,
                "tier_cost_usd": tier_cost,
            }
        )

        remaining -= tier_capacity
        if upper_limit is not None:
            prev_limit = upper_limit

    return breakdown, round(total_cost, 2)


def _looks_like_lead(record: dict[str, Any]) -> bool:
    lead_markers = [
        "email",
        "work_email",
        "phone",
        "mobile",
        "name",
        "full_name",
        "first_name",
        "last_name",
        "job_title",
        "title",
        "position",
    ]
    return any(_coerce_text(record.get(marker)) for marker in lead_markers)


def _extract_company_name(company: dict[str, Any], fallback_index: int) -> str:
    return _first_non_empty(
        company,
        [
            "company_name",
            "company",
            "name",
            "business_name",
            "organization",
            "domain",
            "website",
        ],
    ) or f"Company {fallback_index}"


def _extract_company_leads(company: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("leads", "contacts", "records", "results", "people"):
        value = company.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if _looks_like_lead(company):
        return [company]
    return []


def _lead_quality(lead: dict[str, Any]) -> dict[str, Any]:
    full_name = _first_non_empty(lead, ["full_name", "fullName", "contact_name", "name"])
    if not full_name:
        first_name = _first_non_empty(lead, ["first_name", "firstName", "first"])
        last_name = _first_non_empty(lead, ["last_name", "lastName", "last"])
        full_name = _safe_full_name("", first_name, last_name)

    job_title = _first_non_empty(lead, ["job_title", "jobTitle", "title", "position", "role"])
    email = _first_non_empty(lead, ["email", "work_email", "business_email"])
    phone = _first_non_empty(lead, ["phone", "mobile", "phone_number", "work_phone"])

    verified_email_statuses = _status_set(
        "QUALIFIED_LEAD_VERIFIED_EMAIL_STATUSES",
        {"valid", "verified", "receiving"},
    )
    verified_phone_statuses = _status_set(
        "QUALIFIED_LEAD_VERIFIED_PHONE_STATUSES",
        {"valid", "verified", "mobile", "landline"},
    )

    email_verified = _coerce_bool(
        lead.get("verified_email")
        or lead.get("email_verified")
        or lead.get("is_email_verified")
    )
    phone_verified = _coerce_bool(
        lead.get("verified_phone")
        or lead.get("phone_verified")
        or lead.get("is_phone_verified")
    )

    email_status = _first_non_empty(
        lead,
        ["email_status", "emailStatus", "email_verification_status", "verification_status"],
    ).lower()
    phone_status = _first_non_empty(
        lead,
        ["phone_status", "phoneStatus", "phone_verification_status", "phone_type"],
    ).lower()

    verified_email = bool(email) and (email_verified or email_status in verified_email_statuses)
    verified_phone = bool(phone) and (phone_verified or phone_status in verified_phone_statuses)

    has_full_name = bool(full_name)
    has_job_title = bool(job_title)
    has_verified_contact = verified_email or verified_phone
    qualified = has_full_name and has_job_title and has_verified_contact
    tier = "A" if qualified and verified_email and verified_phone else ("B" if qualified else "")

    rejection_reasons: list[str] = []
    if not has_full_name:
        rejection_reasons.append("missing_full_name")
    if not has_job_title:
        rejection_reasons.append("missing_job_title")
    if not has_verified_contact:
        rejection_reasons.append("missing_verified_email_or_phone")

    return {
        "qualified": qualified,
        "tier": tier,
        "full_name": full_name,
        "job_title": job_title,
        "email": email,
        "phone": phone,
        "verified_email": verified_email,
        "verified_phone": verified_phone,
        "rejection_reasons": rejection_reasons,
    }


def _analyze_companies_for_export(
    *,
    companies: list[dict[str, Any]],
    unit_price_usd: float,
    max_sample_leads: int,
) -> dict[str, Any]:
    if not companies:
        raise ValueError("At least one company payload is required.")

    breakdown: list[dict[str, Any]] = []
    sample_qualified_leads: list[dict[str, Any]] = []

    total_found = 0
    total_qualified = 0
    total_tier_a = 0
    total_tier_b = 0

    for index, company in enumerate(companies, start=1):
        company_name = _extract_company_name(company, index)
        leads = _extract_company_leads(company)

        found_count = len(leads)
        qualified_count = 0
        tier_a_count = 0
        tier_b_count = 0
        rejected = Counter()

        for lead in leads:
            quality = _lead_quality(lead)
            if quality["qualified"]:
                qualified_count += 1
                if quality["tier"] == "A":
                    tier_a_count += 1
                else:
                    tier_b_count += 1

                if len(sample_qualified_leads) < max_sample_leads:
                    sample_qualified_leads.append(
                        {
                            "company_name": company_name,
                            "full_name": quality["full_name"],
                            "job_title": quality["job_title"],
                            "email": quality["email"],
                            "phone": quality["phone"],
                            "tier": quality["tier"],
                        }
                    )
            else:
                for reason in quality["rejection_reasons"]:
                    rejected[reason] += 1

        total_found += found_count
        total_qualified += qualified_count
        total_tier_a += tier_a_count
        total_tier_b += tier_b_count

        company_total = round(qualified_count * unit_price_usd, 2)
        breakdown.append(
            {
                "company_name": company_name,
                "leads_found": found_count,
                "qualified_leads": qualified_count,
                "tier_a_leads": tier_a_count,
                "tier_b_leads": tier_b_count,
                "unit_price_usd": unit_price_usd,
                "estimated_total_usd": company_total,
                "rejection_reasons": dict(rejected),
            }
        )

    estimated_total = round(total_qualified * unit_price_usd, 2)
    cost_per_qualified = round(estimated_total / total_qualified, 2) if total_qualified > 0 else 0.0

    return {
        "qualification_rule": "full_name AND job_title AND (verified_email OR verified_phone)",
        "pricing_model": "flat_per_qualified_lead",
        "unit_price_usd": unit_price_usd,
        "summary": {
            "companies_count": len(companies),
            "leads_found": total_found,
            "qualified_leads": total_qualified,
            "tier_a_leads": total_tier_a,
            "tier_b_leads": total_tier_b,
            "estimated_total_usd": estimated_total,
            "cost_per_qualified_lead_usd": cost_per_qualified,
        },
        "company_breakdown": breakdown,
        "sample_qualified_leads": sample_qualified_leads,
    }


def _ledger_path() -> Path:
    raw = os.getenv("EXPORT_BILLING_LEDGER_PATH", "/tmp/leadsmcp_export_billing_ledger.jsonl").strip()
    return Path(raw)


def _append_ledger_record(record: dict[str, Any]) -> None:
    try:
        path = _ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        # Non-fatal: Stripe idempotency key is still the primary charge guard.
        return


def _ledger_key(*, tenant_id: str, stripe_customer_id: str, export_batch_id: str) -> str:
    normalized_tenant = tenant_id.strip() or "default"
    return f"{normalized_tenant}:{stripe_customer_id.strip()}:{export_batch_id.strip()}"


async def _fetch_customer_export_access(
    *,
    stripe_customer_id: str,
    price_id: str = "",
) -> dict[str, Any]:
    target_price = price_id.strip() or os.getenv("STRIPE_METERED_PRICE_ID", "").strip()
    subscriptions = await _stripe_request(
        "GET",
        "/subscriptions",
        params={
            "customer": stripe_customer_id.strip(),
            "status": "all",
            "limit": 20,
        },
    )

    data = subscriptions.get("data", [])
    matching_subscriptions = []

    for sub in data:
        if not isinstance(sub, dict):
            continue
        if not target_price:
            matching_subscriptions.append(sub)
            continue

        items = sub.get("items", {}).get("data", [])
        if any(
            isinstance(item, dict)
            and isinstance(item.get("price"), dict)
            and item["price"].get("id") == target_price
            for item in items
        ):
            matching_subscriptions.append(sub)

    access_statuses = {"active", "trialing"}
    has_access = any(
        isinstance(sub, dict) and str(sub.get("status", "")).lower() in access_statuses
        for sub in matching_subscriptions
    )

    latest_subscription = matching_subscriptions[0] if matching_subscriptions else None
    latest_status = latest_subscription.get("status") if isinstance(latest_subscription, dict) else None

    return {
        "stripe_customer_id": stripe_customer_id.strip(),
        "price_id": target_price or None,
        "has_export_access": has_access,
        "latest_subscription_status": latest_status,
        "subscription_count": len(matching_subscriptions),
    }


async def _create_checkout_session(
    *,
    stripe_customer_id: str,
    success_url: str,
    cancel_url: str,
    price_id: str = "",
) -> dict[str, Any]:
    selected_price = price_id.strip() or os.getenv("STRIPE_METERED_PRICE_ID", "").strip()
    if not selected_price:
        raise ValueError("Missing price_id and STRIPE_METERED_PRICE_ID is not set.")

    session = await _stripe_request(
        "POST",
        "/checkout/sessions",
        data={
            "mode": "subscription",
            "customer": stripe_customer_id.strip(),
            "line_items[0][price]": selected_price,
            "success_url": success_url.strip(),
            "cancel_url": cancel_url.strip(),
            "allow_promotion_codes": "true",
        },
    )

    return {
        "checkout_session_id": session.get("id"),
        "checkout_url": session.get("url"),
        "stripe_customer_id": stripe_customer_id.strip(),
        "price_id": selected_price,
    }


@mcp.tool()
async def ensure_customer_profile(
    email: str,
    first_name: str,
    last_name: str,
    phone: str = "",
    full_name: str = "",
) -> dict[str, Any]:
    """
    Create or update a Stripe customer profile for LeadsMCP.
    Use this before showing full lead results or allowing CRM export.
    """
    if "@" not in email:
        raise ValueError("A valid email is required.")
    if not first_name.strip() or not last_name.strip():
        raise ValueError("Both first_name and last_name are required.")

    normalized_full_name = _safe_full_name(full_name, first_name, last_name)
    customer_payload = _normalize_customer_payload(
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        full_name=normalized_full_name,
    )

    customer_list = await _stripe_request(
        "GET",
        "/customers",
        params={"email": email.strip(), "limit": 1},
    )
    existing_customers = customer_list.get("data", [])
    existing_customer = next(
        (
            customer
            for customer in existing_customers
            if isinstance(customer, dict) and not customer.get("deleted", False)
        ),
        None,
    )

    if isinstance(existing_customer, dict) and existing_customer.get("id"):
        customer_id = str(existing_customer["id"])
        updated = await _stripe_request(
            "POST",
            f"/customers/{customer_id}",
            data=customer_payload,
        )
        return {
            "created": False,
            "customer_id": updated.get("id"),
            "stripe_customer_id": updated.get("id"),
            "full_name": normalized_full_name,
            "email": email.strip(),
            "phone": phone.strip(),
        }

    created = await _stripe_request("POST", "/customers", data=customer_payload)
    return {
        "created": True,
        "customer_id": created.get("id"),
        "stripe_customer_id": created.get("id"),
        "full_name": normalized_full_name,
        "email": email.strip(),
        "phone": phone.strip(),
    }


@mcp.tool()
async def estimate_qualified_lead_export_cost(
    leads_exported: int = 0,
    qualified_leads: int = 0,
    unit_price_usd: float = 0.0,
) -> dict[str, Any]:
    """
    Estimate export cost.

    Compatibility behavior:
    - If `qualified_leads` is provided, uses flat per-qualified-lead pricing.
    - Else, if `leads_exported` is provided, uses legacy graduated estimation.
    """
    if qualified_leads > 0:
        final_unit_price = _qualified_lead_unit_price(unit_price_usd)
        total = round(qualified_leads * final_unit_price, 2)
        return {
            "qualified_leads": qualified_leads,
            "currency": "usd",
            "pricing_model": "flat_per_qualified_lead",
            "unit_price_usd": final_unit_price,
            "estimated_total_usd": total,
        }

    if leads_exported <= 0:
        raise ValueError("Provide either qualified_leads > 0 or leads_exported > 0.")

    breakdown, total = _graduated_tier_breakdown(leads_exported)
    return {
        "leads_exported": leads_exported,
        "currency": "usd",
        "pricing_model": "graduated",
        "estimated_total_usd": total,
        "breakdown": breakdown,
    }


@mcp.tool()
async def analyze_qualified_lead_export(
    companies: list[dict[str, Any]],
    unit_price_usd: float = 0.0,
    max_sample_leads: int = 10,
) -> dict[str, Any]:
    """
    Analyze lead payloads and calculate billable qualified leads by company.

    Qualification rule:
      full_name AND job_title AND (verified_email OR verified_phone)
    """
    final_unit_price = _qualified_lead_unit_price(unit_price_usd)
    sample_cap = max(1, min(max_sample_leads, 50))
    return _analyze_companies_for_export(
        companies=companies,
        unit_price_usd=final_unit_price,
        max_sample_leads=sample_cap,
    )


@mcp.tool()
async def create_usage_checkout_session(
    stripe_customer_id: str,
    success_url: str,
    cancel_url: str,
    price_id: str = "",
) -> dict[str, Any]:
    """
    Create a Stripe Checkout session for a metered subscription.
    """
    if not stripe_customer_id.strip():
        raise ValueError("stripe_customer_id is required.")
    if not success_url.strip() or not cancel_url.strip():
        raise ValueError("Both success_url and cancel_url are required.")

    return await _create_checkout_session(
        stripe_customer_id=stripe_customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        price_id=price_id,
    )


@mcp.tool()
async def get_customer_export_access(
    stripe_customer_id: str,
    price_id: str = "",
) -> dict[str, Any]:
    """
    Check if a customer has an active/trialing subscription for export access.
    """
    if not stripe_customer_id.strip():
        raise ValueError("stripe_customer_id is required.")

    access = await _fetch_customer_export_access(
        stripe_customer_id=stripe_customer_id,
        price_id=price_id,
    )
    access["consent_mode"] = _billing_consent_mode()
    access["requires_explicit_permission"] = _billing_consent_mode() == "per_batch"
    return access


@mcp.tool()
async def plan_qualified_lead_export_billing(
    stripe_customer_id: str,
    qualified_leads: int,
    export_batch_id: str = "",
    tenant_id: str = "",
    consent_granted: bool = False,
    success_url: str = "",
    cancel_url: str = "",
    price_id: str = "",
    unit_price_usd: float = 0.0,
    auto_create_checkout: bool = True,
) -> dict[str, Any]:
    """
    Decide the next billing step for an export batch.

    Outcomes:
    - checkout_required
    - permission_required
    - ready_to_export
    """
    if not stripe_customer_id.strip():
        raise ValueError("stripe_customer_id is required.")
    if qualified_leads <= 0:
        raise ValueError("qualified_leads must be greater than 0.")

    final_unit_price = _qualified_lead_unit_price(unit_price_usd)
    estimated_total_usd = round(qualified_leads * final_unit_price, 2)
    consent_mode = _billing_consent_mode()

    access = await _fetch_customer_export_access(
        stripe_customer_id=stripe_customer_id,
        price_id=price_id,
    )

    response: dict[str, Any] = {
        "stripe_customer_id": stripe_customer_id.strip(),
        "tenant_id": tenant_id.strip() or None,
        "export_batch_id": export_batch_id.strip() or None,
        "qualified_leads": qualified_leads,
        "unit_price_usd": final_unit_price,
        "estimated_total_usd": estimated_total_usd,
        "consent_mode": consent_mode,
        "has_export_access": access["has_export_access"],
        "checkout_required": False,
        "permission_required": False,
        "ready_to_export": False,
        "next_action": "",
    }

    if not access["has_export_access"]:
        response["checkout_required"] = True
        response["next_action"] = "checkout_required"
        if auto_create_checkout and success_url.strip() and cancel_url.strip():
            checkout = await _create_checkout_session(
                stripe_customer_id=stripe_customer_id,
                success_url=success_url,
                cancel_url=cancel_url,
                price_id=price_id,
            )
            response["checkout"] = checkout
        else:
            response["message"] = (
                "Customer has no active export subscription. "
                "Call stripe_create_usage_checkout_session to collect access."
            )
        return response

    if consent_mode == "per_batch" and not consent_granted:
        response["permission_required"] = True
        response["next_action"] = "permission_required"
        response["message"] = (
            "Customer has access but explicit per-batch billing permission is required. "
            "Collect confirmation and retry with consent_granted=true."
        )
        return response

    response["ready_to_export"] = True
    response["next_action"] = "ready_to_export"
    response["message"] = "Billing checks passed. Export can proceed."
    return response


@mcp.tool()
async def record_qualified_lead_export(
    stripe_customer_id: str,
    leads_exported: int = 1,
    export_batch_id: str = "",
    tenant_id: str = "",
    consent_granted: bool = False,
    tier_a_leads: int = 0,
    tier_b_leads: int = 0,
    timestamp: int = 0,
    idempotency_key: str = "",
    event_name: str = "",
) -> dict[str, Any]:
    """
    Record a usage event for qualified lead export billing with batch guards.

    Recommended:
      - pass export_batch_id
      - pass consent_granted=true when BILLING_CONSENT_MODE=per_batch
    """
    if not stripe_customer_id.strip():
        raise ValueError("stripe_customer_id is required.")

    if tier_a_leads > 0 or tier_b_leads > 0:
        qualified_leads = tier_a_leads + tier_b_leads
    else:
        qualified_leads = leads_exported

    if qualified_leads <= 0:
        raise ValueError("At least one qualified lead must be exported.")

    if _require_export_batch_id() and not export_batch_id.strip():
        raise ValueError(
            "export_batch_id is required when BILLING_REQUIRE_EXPORT_BATCH_ID=true."
        )

    consent_mode = _billing_consent_mode()
    if consent_mode == "per_batch" and not consent_granted:
        raise ValueError(
            "Explicit billing permission is required for this export batch. "
            "Retry with consent_granted=true after user confirmation."
        )

    if _enforce_export_access_check():
        access = await _fetch_customer_export_access(stripe_customer_id=stripe_customer_id)
        if not access["has_export_access"]:
            raise ValueError(
                "Customer has no active export access. "
                "Complete checkout before recording usage."
            )

    ledger_key = ""
    if export_batch_id.strip():
        ledger_key = _ledger_key(
            tenant_id=tenant_id,
            stripe_customer_id=stripe_customer_id,
            export_batch_id=export_batch_id,
        )
        existing = _EXPORT_BILLING_LEDGER.get(ledger_key)
        if existing:
            return {
                **existing,
                "already_recorded": True,
                "guarded_by_batch_ledger": True,
            }

    selected_event_name = event_name.strip() or os.getenv("STRIPE_METER_EVENT_NAME", DEFAULT_METER_EVENT_NAME)
    value_field = os.getenv("STRIPE_METER_VALUE_FIELD", DEFAULT_METER_VALUE_FIELD).strip()
    customer_field = os.getenv("STRIPE_METER_CUSTOMER_FIELD", DEFAULT_METER_CUSTOMER_FIELD).strip()
    event_timestamp = timestamp if timestamp > 0 else int(time.time())

    event_data = {
        "event_name": selected_event_name,
        "timestamp": str(event_timestamp),
        f"payload[{customer_field}]": stripe_customer_id.strip(),
        f"payload[{value_field}]": str(qualified_leads),
        "payload[leads_exported]": str(qualified_leads),
        "payload[tier_a_leads]": str(max(tier_a_leads, 0)),
        "payload[tier_b_leads]": str(max(tier_b_leads, 0)),
    }
    if export_batch_id.strip():
        event_data["payload[export_batch_id]"] = export_batch_id.strip()
    if tenant_id.strip():
        event_data["payload[tenant_id]"] = tenant_id.strip()

    final_idempotency_key = idempotency_key.strip()
    if not final_idempotency_key:
        if export_batch_id.strip():
            normalized_tenant = tenant_id.strip() or "default"
            final_idempotency_key = (
                f"{selected_event_name}:{stripe_customer_id.strip()}:{normalized_tenant}:{export_batch_id.strip()}"
            )
        else:
            final_idempotency_key = (
                f"{selected_event_name}:{stripe_customer_id.strip()}:{event_timestamp}:{qualified_leads}"
            )

    meter_event = await _stripe_request(
        "POST",
        "/billing/meter_events",
        data=event_data,
        idempotency_key=final_idempotency_key,
    )

    result = {
        "meter_event_id": meter_event.get("identifier") or meter_event.get("id"),
        "event_name": selected_event_name,
        "stripe_customer_id": stripe_customer_id.strip(),
        "tenant_id": tenant_id.strip() or None,
        "export_batch_id": export_batch_id.strip() or None,
        "qualified_leads": qualified_leads,
        "tier_a_leads": max(tier_a_leads, 0),
        "tier_b_leads": max(tier_b_leads, 0),
        "timestamp": event_timestamp,
        "consent_mode": consent_mode,
        "consent_granted": consent_granted,
        "idempotency_key": final_idempotency_key,
        "already_recorded": False,
        "guarded_by_batch_ledger": bool(ledger_key),
        "raw": meter_event,
    }

    if ledger_key:
        _EXPORT_BILLING_LEDGER[ledger_key] = result
        _append_ledger_record(
            {
                "ledger_key": ledger_key,
                "recorded_at": int(time.time()),
                "result": result,
            }
        )

    return result
