"""Deterministic HighLevel *create contact* logic.

This module implements the pure, side-effect-free pieces of the
``ghl_contacts_create_contact`` tool so they can be unit tested without a live MCP
session or a live HighLevel account:

  * ``build_create_contact_body`` — validate inputs, normalise safely, inject the
    authoritative ``locationId`` into the JSON body.
  * ``map_create_contact_response`` — turn an upstream HTTP status + JSON body into a
    success dict or a structured, redacted :class:`ContactCreateError`.
  * ``redact_secrets`` — scrub tokens/secrets out of anything echoed back to a client.

The tool wiring in ``main.py`` resolves per-request tenant credentials, calls
``build_create_contact_body``, POSTs to the official ``POST /contacts/`` REST endpoint,
and passes the response through ``map_create_contact_response``.

There is deliberately **no dry-run / preview / validateOnly path**: HighLevel's API does
not support one, so faking it would either lie to the caller or send an unknown field the
API rejects. The only way to "preview" is to inspect the returned body of the single real
call.
"""

from __future__ import annotations

from typing import Any

# Named fields we forward verbatim (when provided) to POST /contacts/. These are all
# documented HighLevel contact fields. ``tags`` and ``customFields`` get light coercion;
# everything else is passed through as-is.
_STRING_FIELDS = (
    "firstName",
    "lastName",
    "name",
    "companyName",
    "email",
    "phone",
    "address1",
    "city",
    "state",
    "postalCode",
    "country",
    "website",
    "timezone",
    "source",
)

# Case-insensitive key fragments whose values must never be echoed back to a client.
_SECRET_KEY_FRAGMENTS = (
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "apikey",
    "x-mcp-secret",
    "password",
    "token",
    "secret",
)

_REDACTED = "***REDACTED***"


class ContactCreateError(Exception):
    """Structured, already-redacted failure from the create-contact workflow.

    ``category`` is a stable machine-readable slug, ``status_code`` is the upstream HTTP
    status (``None`` for local validation failures), ``hint`` is an actionable operator
    message, and ``response`` is the redacted upstream body (if any).
    """

    def __init__(
        self,
        category: str,
        hint: str,
        *,
        status_code: int | None = None,
        response: Any = None,
    ) -> None:
        self.category = category
        self.hint = hint
        self.status_code = status_code
        self.response = response
        super().__init__(hint)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "error": self.category,
            "message": self.hint,
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        if self.response is not None:
            payload["upstream_response"] = self.response
        return payload


def redact_secrets(value: Any) -> Any:
    """Recursively mask token/secret values and any ``Bearer ...`` strings."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and any(
                fragment in key.lower() for fragment in _SECRET_KEY_FRAGMENTS
            ):
                redacted[key] = _REDACTED
            else:
                redacted[key] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str) and value.strip().lower().startswith("bearer "):
        return _REDACTED
    return value


def _coerce_tags(tags: Any) -> list[str] | None:
    if tags is None:
        return None
    if isinstance(tags, str):
        tag = tags.strip()
        return [tag] if tag else None
    if isinstance(tags, (list, tuple, set)):
        cleaned = [str(t).strip() for t in tags if str(t).strip()]
        return cleaned or None
    raise ContactCreateError(
        "validation_error",
        "tags must be a string or a list of strings.",
    )


def _coerce_custom_fields(custom_fields: Any) -> list[Any] | None:
    """Accept HighLevel's native array form, or a {id: value} dict for convenience."""
    if custom_fields is None:
        return None
    if isinstance(custom_fields, list):
        return custom_fields or None
    if isinstance(custom_fields, dict):
        converted = [{"id": key, "value": val} for key, val in custom_fields.items()]
        return converted or None
    raise ContactCreateError(
        "validation_error",
        "customFields must be a list of {id,value} objects or an {id: value} mapping.",
    )


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_create_contact_body(
    *,
    location_id: str | None,
    fields: dict[str, Any],
    tags: Any = None,
    custom_fields: Any = None,
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate + normalise inputs and return the JSON body for POST /contacts/.

    ``fields`` holds the named string fields (see ``_STRING_FIELDS``). Raises
    :class:`ContactCreateError` (category ``missing_location`` / ``missing_identifier`` /
    ``validation_error``) before any network call is attempted.
    """
    resolved_location = _clean_str(location_id)
    if not resolved_location:
        raise ContactCreateError(
            "missing_location",
            "No locationId available. Provide it via the locationId argument, the "
            "x-ghl-location-id request header, or the GHL_LOCATION_ID environment "
            "variable. HighLevel writes are scoped to a single location.",
        )

    # Pass-through fields first so explicit named params win; locationId is forced last.
    body: dict[str, Any] = {}
    if additional_fields:
        if not isinstance(additional_fields, dict):
            raise ContactCreateError(
                "validation_error", "additionalFields must be an object/dict."
            )
        body.update({k: v for k, v in additional_fields.items() if k != "locationId"})

    normalized: dict[str, Any] = {}
    for key in _STRING_FIELDS:
        cleaned = _clean_str(fields.get(key))
        if cleaned is None:
            continue
        normalized[key] = cleaned.lower() if key == "email" else cleaned

    email = normalized.get("email")
    if email is not None and ("@" not in email or "." not in email.split("@")[-1]):
        raise ContactCreateError(
            "validation_error", f"email does not look like a valid address: {email!r}"
        )

    phone = normalized.get("phone")
    if email is None and phone is None:
        raise ContactCreateError(
            "missing_identifier",
            "At least one contact identifier is required: provide email or phone.",
        )

    body.update(normalized)

    coerced_tags = _coerce_tags(tags)
    if coerced_tags is not None:
        body["tags"] = coerced_tags

    coerced_custom = _coerce_custom_fields(custom_fields)
    if coerced_custom is not None:
        body["customFields"] = coerced_custom

    body["locationId"] = resolved_location
    return body


def _extract_contact_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    contact = payload.get("contact")
    if isinstance(contact, dict) and contact.get("id"):
        return str(contact["id"])
    for key in ("contactId", "id"):
        if payload.get(key):
            return str(payload[key])
    meta = payload.get("meta")
    if isinstance(meta, dict) and meta.get("contactId"):
        return str(meta["contactId"])
    return None


def map_create_contact_response(status_code: int, payload: Any) -> dict[str, Any]:
    """Return a success dict for 2xx, else raise a structured ContactCreateError.

    The upstream body is always redacted before it is surfaced.
    """
    redacted = redact_secrets(payload)

    if 200 <= status_code < 300:
        contact_id = _extract_contact_id(payload)
        return {
            "ok": True,
            "status": "created",
            "contactId": contact_id,
            "contact": redacted.get("contact") if isinstance(redacted, dict) else None,
            "raw": redacted,
        }

    if status_code in (400, 422):
        raise ContactCreateError(
            "validation_error",
            "HighLevel rejected the contact payload. Check required fields and formats "
            "(email/phone, custom field ids) against ghl_describe_operation output.",
            status_code=status_code,
            response=redacted,
        )

    if status_code == 401:
        raise ContactCreateError(
            "auth_error",
            "HighLevel rejected the token (401). The Authorization token is missing, "
            "invalid, or expired. Provide a valid PIT/OAuth token via x-ghl-token or "
            "GHL_PIT_TOKEN.",
            status_code=status_code,
            response=redacted,
        )

    if status_code == 403:
        raise ContactCreateError(
            "scope_or_location_error",
            "HighLevel denied the write (403). The token is likely missing the "
            "'contacts.write' scope, or the locationId does not match the token's "
            "authorized location. Grant contacts.write and confirm the location.",
            status_code=status_code,
            response=redacted,
        )

    if status_code == 409:
        contact_id = _extract_contact_id(payload)
        detail = f" Existing contactId: {contact_id}." if contact_id else ""
        raise ContactCreateError(
            "duplicate_contact",
            "A contact with this email/phone already exists in the location (409). "
            "Use the upsert tool or fetch/update the existing record instead." + detail,
            status_code=status_code,
            response=redacted,
        )

    raise ContactCreateError(
        "upstream_error",
        f"HighLevel returned an unexpected status ({status_code}).",
        status_code=status_code,
        response=redacted,
    )
