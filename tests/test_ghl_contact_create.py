"""Regression tests for the deterministic GHL create/upsert contact tools."""

from __future__ import annotations

import json

import httpx
import pytest

from ghl_contact_create import (
    ContactCreateError,
    build_create_contact_body,
    map_create_contact_response,
    redact_secrets,
)


# ── build_create_contact_body ────────────────────────────────────────────────

def test_build_success_minimal_email():
    body = build_create_contact_body(
        location_id="LOC123", fields={"email": "Jane@Example.COM", "firstName": "Jane"}
    )
    assert body["email"] == "jane@example.com"  # safely lowercased
    assert body["firstName"] == "Jane"
    assert body["locationId"] == "LOC123"


def test_build_injects_location_into_body():
    body = build_create_contact_body(location_id="LOC-XYZ", fields={"phone": "+15551234567"})
    assert body["locationId"] == "LOC-XYZ"


def test_build_missing_location_raises():
    with pytest.raises(ContactCreateError) as exc:
        build_create_contact_body(location_id="  ", fields={"email": "a@b.com"})
    assert exc.value.category == "missing_location"


def test_build_missing_identifier_raises():
    with pytest.raises(ContactCreateError) as exc:
        build_create_contact_body(location_id="LOC", fields={"firstName": "NoContact"})
    assert exc.value.category == "missing_identifier"


def test_build_invalid_email_raises():
    with pytest.raises(ContactCreateError) as exc:
        build_create_contact_body(location_id="LOC", fields={"email": "not-an-email"})
    assert exc.value.category == "validation_error"


def test_build_phone_only_is_valid():
    body = build_create_contact_body(location_id="LOC", fields={"phone": " +1 555 000 "})
    assert body["phone"] == "+1 555 000"  # trimmed, not reformatted
    assert "email" not in body


def test_build_tags_string_coerced_to_list():
    body = build_create_contact_body(
        location_id="LOC", fields={"email": "a@b.com"}, tags="outscraper"
    )
    assert body["tags"] == ["outscraper"]


def test_build_custom_fields_dict_converted_to_array():
    body = build_create_contact_body(
        location_id="LOC", fields={"email": "a@b.com"}, custom_fields={"cf_1": "v"}
    )
    assert body["customFields"] == [{"id": "cf_1", "value": "v"}]


def test_build_additional_fields_passthrough_but_location_forced():
    body = build_create_contact_body(
        location_id="LOC-REAL",
        fields={"email": "a@b.com"},
        additional_fields={"dnd": True, "locationId": "LOC-SPOOFED"},
    )
    assert body["dnd"] is True
    assert body["locationId"] == "LOC-REAL"  # caller cannot spoof location via passthrough


def test_build_all_documented_fields():
    body = build_create_contact_body(
        location_id="LOC",
        fields={
            "firstName": "Jane", "lastName": "Doe", "name": "Jane Doe",
            "companyName": "Example LLC", "email": "a@b.com", "phone": "+15551234567",
            "address1": "1 Main St", "city": "Austin", "state": "TX",
            "postalCode": "78701", "country": "US", "website": "https://ex.com",
            "timezone": "America/Chicago", "source": "leadsmcp",
        },
        tags=["outscraper", "austin"],
    )
    for key in ("firstName", "lastName", "companyName", "phone", "address1", "city",
                "state", "postalCode", "country", "website", "timezone", "source"):
        assert key in body


# ── map_create_contact_response ──────────────────────────────────────────────

def test_map_success_extracts_contact_id():
    result = map_create_contact_response(201, {"contact": {"id": "C-1", "email": "a@b.com"}})
    assert result["ok"] is True
    assert result["status"] == "created"
    assert result["contactId"] == "C-1"


def test_map_scope_failure_calls_out_contacts_write():
    with pytest.raises(ContactCreateError) as exc:
        map_create_contact_response(403, {"message": "forbidden"})
    assert exc.value.category == "scope_or_location_error"
    assert "contacts.write" in exc.value.hint


def test_map_validation_failure():
    with pytest.raises(ContactCreateError) as exc:
        map_create_contact_response(422, {"message": "invalid"})
    assert exc.value.category == "validation_error"
    assert exc.value.status_code == 422


def test_map_auth_failure():
    with pytest.raises(ContactCreateError) as exc:
        map_create_contact_response(401, {"message": "unauthorized"})
    assert exc.value.category == "auth_error"


def test_map_duplicate_conflict_includes_existing_id():
    with pytest.raises(ContactCreateError) as exc:
        map_create_contact_response(409, {"meta": {"contactId": "DUP-9"}})
    assert exc.value.category == "duplicate_contact"
    assert "DUP-9" in exc.value.hint


def test_map_unexpected_status():
    with pytest.raises(ContactCreateError) as exc:
        map_create_contact_response(500, {"message": "boom"})
    assert exc.value.category == "upstream_error"


# ── redaction ────────────────────────────────────────────────────────────────

def test_redact_masks_secret_keys_and_bearer():
    payload = {
        "access_token": "pit-super-secret",
        "authorization": "Bearer abc",
        "nested": {"client_secret": "shh", "keep": "visible"},
        "header": "Bearer leaked-token",
        "list": [{"api_key": "key-material-99"}, "plain"],
    }
    red = redact_secrets(payload)
    blob = json.dumps(red)
    assert "pit-super-secret" not in blob
    assert "shh" not in blob
    assert "leaked-token" not in blob
    assert "key-material-99" not in blob
    assert red["list"][0]["api_key"] == "***REDACTED***"
    assert red["nested"]["keep"] == "visible"
    assert red["list"][1] == "plain"


def test_map_error_response_is_redacted():
    with pytest.raises(ContactCreateError) as exc:
        map_create_contact_response(403, {"token": "pit-leak", "message": "no scope"})
    assert "pit-leak" not in json.dumps(exc.value.to_dict())


def test_error_to_dict_shape():
    err = ContactCreateError("validation_error", "bad", status_code=422, response={"m": 1})
    d = err.to_dict()
    assert d == {
        "ok": False,
        "error": "validation_error",
        "message": "bad",
        "status_code": 422,
        "upstream_response": {"m": 1},
    }


# ── HTTP wiring via httpx.MockTransport ──────────────────────────────────────

@pytest.mark.asyncio
async def test_post_create_contact_sends_body_and_headers_and_parses():
    import main

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["version"] = request.headers.get("Version")
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"contact": {"id": "C-77"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        status, payload = await main._post_create_contact(
            "https://services.leadconnectorhq.com/contacts/",
            headers={"Authorization": "Bearer pit-xyz", "Version": "2021-07-28"},
            body={"email": "a@b.com", "locationId": "LOC"},
            http_client=client,
        )
    finally:
        await client.aclose()

    assert status == 201
    assert payload["contact"]["id"] == "C-77"
    assert captured["url"].endswith("/contacts/")
    assert captured["body"]["locationId"] == "LOC"
    assert captured["auth"] == "Bearer pit-xyz"


# ── End-to-end tool call through the MCP server (network + creds mocked) ──────

@pytest.mark.asyncio
async def test_tool_create_contact_success(monkeypatch):
    import main
    from fastmcp import Client

    monkeypatch.setattr(
        main, "_resolve_ghl_rest_credentials",
        lambda: ("Bearer pit-xyz", "LOC-DEFAULT", "2021-07-28"),
    )

    async def fake_post(url, *, headers, body, http_client=None):
        assert url.endswith("/contacts/upsert")
        assert body["locationId"] == "LOC-DEFAULT"  # injected from resolved creds
        return 201, {"contact": {"id": "C-100"}}

    monkeypatch.setattr(main, "_post_create_contact", fake_post)

    async with Client(main.orchestrator) as c:
        res = await c.call_tool(
            "crm_import_contact",
            {
                "email": "jane@example.com",
                "firstName": "Jane",
                "confirm": True,
            },
        )
    assert res.structured_content["contactId"] == "C-100"
    assert res.structured_content["status"] == "created"


@pytest.mark.asyncio
async def test_tool_create_contact_missing_location_raises(monkeypatch):
    import main
    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    monkeypatch.setattr(
        main, "_resolve_ghl_rest_credentials", lambda: ("Bearer pit-xyz", "", "2021-07-28")
    )

    async with Client(main.orchestrator) as c:
        with pytest.raises(ToolError) as exc:
            await c.call_tool(
                "crm_import_contact",
                {"email": "a@b.com", "confirm": True},
            )
    assert "missing_location" in str(exc.value)


@pytest.mark.asyncio
async def test_tool_create_contact_scope_failure_maps_error(monkeypatch):
    import main
    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    monkeypatch.setattr(
        main, "_resolve_ghl_rest_credentials",
        lambda: ("Bearer pit-xyz", "LOC", "2021-07-28"),
    )

    async def fake_post(url, *, headers, body, http_client=None):
        return 403, {"message": "forbidden", "token": "pit-leak"}

    monkeypatch.setattr(main, "_post_create_contact", fake_post)

    async with Client(main.orchestrator) as c:
        with pytest.raises(ToolError) as exc:
            await c.call_tool(
                "crm_import_contact",
                {"phone": "+15551234567", "confirm": True},
            )
    message = str(exc.value)
    assert "scope_or_location_error" in message
    assert "pit-leak" not in message  # secret redacted end-to-end


@pytest.mark.asyncio
async def test_tool_upsert_reports_updated(monkeypatch):
    import main
    from fastmcp import Client

    monkeypatch.setattr(
        main, "_resolve_ghl_rest_credentials",
        lambda: ("Bearer pit-xyz", "LOC", "2021-07-28"),
    )

    async def fake_post(url, *, headers, body, http_client=None):
        assert url.endswith("/contacts/upsert")
        return 200, {"contact": {"id": "C-5"}, "new": False}

    monkeypatch.setattr(main, "_post_create_contact", fake_post)

    async with Client(main.orchestrator) as c:
        res = await c.call_tool(
            "crm_import_contact",
            {"email": "a@b.com", "confirm": True},
        )
    assert res.structured_content["status"] == "updated"
    assert res.structured_content["contactId"] == "C-5"
