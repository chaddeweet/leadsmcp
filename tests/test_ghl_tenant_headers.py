"""Regression tests for tenant-aware GHL header forwarding.

Locks in the per-request credential precedence and one-time Bearer normalisation used
by GHLTenantAwareTransport, independent of a live MCP session.
"""

from __future__ import annotations

from main import build_ghl_tenant_headers


def test_x_ghl_token_takes_precedence_over_authorization():
    headers = build_ghl_tenant_headers(
        {"x-ghl-token": "pit-tenant", "authorization": "Bearer server-default"}
    )
    assert headers["authorization"] == "Bearer pit-tenant"


def test_bare_token_gets_bearer_prefix_once():
    assert build_ghl_tenant_headers({"x-ghl-token": "pit-abc"})["authorization"] == "Bearer pit-abc"


def test_existing_bearer_is_not_double_prefixed():
    headers = build_ghl_tenant_headers({"authorization": "Bearer pit-abc"})
    assert headers["authorization"] == "Bearer pit-abc"


def test_bearer_prefix_is_case_insensitive():
    headers = build_ghl_tenant_headers({"authorization": "bearer pit-abc"})
    # Already prefixed (any case) -> forwarded unchanged, not "Bearer bearer ...".
    assert headers["authorization"] == "bearer pit-abc"


def test_location_precedence_and_trim():
    headers = build_ghl_tenant_headers(
        {"x-ghl-location-id": " LOC-TENANT ", "locationid": "LOC-NATIVE"}
    )
    assert headers["locationid"] == "LOC-TENANT"


def test_location_falls_back_to_native_header():
    headers = build_ghl_tenant_headers({"locationid": "LOC-NATIVE"})
    assert headers["locationid"] == "LOC-NATIVE"


def test_version_forwarded_when_present():
    headers = build_ghl_tenant_headers({"x-ghl-version": "2021-07-28"})
    assert headers["version"] == "2021-07-28"


def test_empty_incoming_yields_no_tenant_headers():
    # No tenant headers => empty dict so the transport falls back to env defaults.
    assert build_ghl_tenant_headers({}) == {}


def test_only_provided_fields_returned():
    headers = build_ghl_tenant_headers({"x-ghl-token": "pit-abc"})
    assert set(headers) == {"authorization"}
