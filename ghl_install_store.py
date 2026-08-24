"""Durable storage for Marketplace installation credentials.

Production Marketplace installs must survive serverless cold starts. Supabase is
therefore mandatory in Marketplace mode. A JSONL backend remains available only
for local/developer use.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

import httpx


DEFAULT_TABLE = "ghl_installations"


class InstallStoreError(RuntimeError):
    pass


def _supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "").strip().rstrip("/")


def _supabase_key() -> str:
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )


def _supabase_table() -> str:
    return (
        os.getenv("SUPABASE_GHL_INSTALLS_TABLE", DEFAULT_TABLE).strip()
        or DEFAULT_TABLE
    )


def supabase_configured() -> bool:
    return bool(_supabase_url() and _supabase_key())


def install_store_backend(env: dict[str, str] | None = None) -> str:
    values = env or os.environ
    requested = values.get("GHL_INSTALL_STORE_BACKEND", "").strip().lower()
    if requested and requested not in {"supabase", "file"}:
        raise InstallStoreError(
            "GHL_INSTALL_STORE_BACKEND must be 'supabase' or 'file'."
        )
    if requested:
        backend = requested
    else:
        backend = "supabase" if supabase_configured() else "file"

    mode = values.get("LEADSMCP_MODE", "marketplace").strip().lower()
    production = (
        values.get("VERCEL_ENV", "").strip().lower() == "production"
        or values.get("ENVIRONMENT", "").strip().lower() == "production"
    )
    if backend == "file" and (mode == "marketplace" or production):
        raise InstallStoreError(
            "Supabase installation storage is required in Marketplace/production "
            "mode. Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    if backend == "supabase" and not supabase_configured():
        raise InstallStoreError(
            "Supabase installation storage is selected but not configured."
        )
    return backend


def _file_path() -> Path:
    raw = os.getenv(
        "GHL_INSTALL_STORE_PATH", "/tmp/leadsmcp_ghl_installs.jsonl"
    ).strip()
    return Path(raw)


def _postgrest_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return (response.text or "").strip()[:300]
    if isinstance(body, dict):
        for key in ("message", "hint", "details", "error", "code"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value[:300]
    return str(body)[:300]


def _headers(*, prefer: str = "") -> dict[str, str]:
    key = _supabase_key()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _table_url(table: str | None = None) -> str:
    return f"{_supabase_url()}/rest/v1/{table or _supabase_table()}"


async def persist_install_record(record: dict[str, Any]) -> dict[str, Any]:
    backend = install_store_backend()
    if backend == "file":
        path = _file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        return {"backend": "file", "store_path": str(path)}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                _table_url(),
                headers=_headers(
                    prefer="resolution=merge-duplicates,return=minimal"
                ),
                params={"on_conflict": "install_key"},
                json=record,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise InstallStoreError(
            f"Supabase install upsert failed ({exc.response.status_code}): "
            f"{_postgrest_detail(exc.response)}"
        ) from exc
    except httpx.RequestError as exc:
        raise InstallStoreError(
            f"Supabase install store unreachable: {type(exc).__name__}"
        ) from exc
    return {"backend": "supabase", "table": _supabase_table()}


async def list_installations(
    *,
    company_id: str = "",
    location_id: str = "",
    installed_only: bool = True,
) -> list[dict[str, Any]]:
    if install_store_backend() == "file":
        return []
    params: dict[str, str] = {
        "select": "*",
        "order": "saved_at.desc",
    }
    if company_id:
        params["company_id"] = f"eq.{company_id}"
    if location_id:
        params["location_id"] = f"eq.{location_id}"
    if installed_only:
        params["installed"] = "eq.true"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            _table_url(),
            headers=_headers(),
            params=params,
        )
    if response.is_error:
        raise InstallStoreError(
            f"Supabase install lookup failed ({response.status_code}): "
            f"{_postgrest_detail(response)}"
        )
    rows = response.json()
    return rows if isinstance(rows, list) else []


async def get_installation(
    *,
    install_key: str = "",
    company_id: str = "",
    location_id: str = "",
    installed_only: bool = True,
) -> dict[str, Any] | None:
    if install_key:
        params: dict[str, str] = {
            "select": "*",
            "install_key": f"eq.{install_key}",
            "limit": "1",
        }
        if installed_only:
            params["installed"] = "eq.true"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                _table_url(),
                headers=_headers(),
                params=params,
            )
        if response.is_error:
            raise InstallStoreError(
                f"Supabase install lookup failed ({response.status_code})."
            )
        rows = response.json()
    else:
        rows = await list_installations(
            company_id=company_id,
            location_id=location_id,
            installed_only=installed_only,
        )
    return rows[0] if isinstance(rows, list) and rows else None


async def patch_installations(
    *,
    values: dict[str, Any],
    company_id: str = "",
    location_id: str = "",
) -> int:
    if not company_id and not location_id:
        raise InstallStoreError("company_id or location_id is required.")
    params: dict[str, str] = {}
    if company_id:
        params["company_id"] = f"eq.{company_id}"
    if location_id:
        params["location_id"] = f"eq.{location_id}"
    values = {
        **values,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.patch(
            _table_url(),
            headers=_headers(prefer="return=representation"),
            params=params,
            json=values,
        )
    if response.is_error:
        raise InstallStoreError(
            f"Supabase install update failed ({response.status_code}): "
            f"{_postgrest_detail(response)}"
        )
    rows = response.json()
    return len(rows) if isinstance(rows, list) else 0


async def mark_uninstalled(
    *,
    company_id: str = "",
    location_id: str = "",
) -> int:
    return await patch_installations(
        company_id=company_id,
        location_id=location_id,
        values={
            "installed": False,
            "access_token_encrypted": "",
            "refresh_token_encrypted": "",
            "uninstalled_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def get_webhook_event(webhook_id: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            _table_url("ghl_webhook_events"),
            headers=_headers(),
            params={
                "select": "*",
                "webhook_id": f"eq.{webhook_id}",
                "limit": "1",
            },
        )
    if response.is_error:
        raise InstallStoreError(
            f"Webhook idempotency lookup failed ({response.status_code})."
        )
    rows = response.json()
    return rows[0] if isinstance(rows, list) and rows else None


async def webhook_event_exists(webhook_id: str) -> bool:
    return await get_webhook_event(webhook_id) is not None


async def record_webhook_event(record: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _table_url("ghl_webhook_events"),
            headers=_headers(
                prefer="resolution=ignore-duplicates,return=minimal"
            ),
            params={"on_conflict": "webhook_id"},
            json=record,
        )
    if response.is_error:
        raise InstallStoreError(
            f"Webhook event persistence failed ({response.status_code})."
        )


async def get_wallet_charge(event_id: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            _table_url("ghl_wallet_charges"),
            headers=_headers(),
            params={
                "select": "*",
                "event_id": f"eq.{event_id}",
                "limit": "1",
            },
        )
    if response.is_error:
        raise InstallStoreError(
            f"Wallet charge lookup failed ({response.status_code})."
        )
    rows = response.json()
    return rows[0] if isinstance(rows, list) and rows else None


async def upsert_wallet_charge(record: dict[str, Any]) -> None:
    record = {
        **record,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _table_url("ghl_wallet_charges"),
            headers=_headers(
                prefer="resolution=merge-duplicates,return=minimal"
            ),
            params={"on_conflict": "event_id"},
            json=record,
        )
    if response.is_error:
        raise InstallStoreError(
            f"Wallet charge persistence failed ({response.status_code})."
        )
