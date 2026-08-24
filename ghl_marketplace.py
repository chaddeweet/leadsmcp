"""HighLevel Marketplace lifecycle, bulk-install, and wallet-charge API client."""

from __future__ import annotations

import os
from typing import Any

import httpx


BASE_URL = "https://services.leadconnectorhq.com"


class MarketplaceAPIError(RuntimeError):
    pass


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Version": os.getenv("GHL_OAUTH_API_VERSION", "v3"),
        "Accept": "application/json",
    }


async def get_installed_locations(
    *,
    agency_access_token: str,
    company_id: str,
    app_id: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(10):
            params: dict[str, Any] = {
                "companyId": company_id,
                "appId": app_id,
                "isInstalled": "true",
                "pageSize": 100,
            }
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(
                f"{BASE_URL}/oauth/installed-locations",
                headers=_headers(agency_access_token),
                params=params,
            )
            if response.is_error:
                raise MarketplaceAPIError(
                    f"Installed-location lookup failed ({response.status_code})."
                )
            payload = response.json()
            page_items = payload.get("items") or []
            if isinstance(page_items, list):
                items.extend(item for item in page_items if isinstance(item, dict))
            pagination = payload.get("pagination") or {}
            if not pagination.get("hasNextPage"):
                break
            page_token = str(pagination.get("nextPageToken") or "")
            if not page_token:
                break
    return items


async def exchange_location_token(
    *,
    agency_access_token: str,
    company_id: str,
    location_id: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/oauth/location-token",
            headers={
                **_headers(agency_access_token),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"companyId": company_id, "locationId": location_id},
        )
    if response.is_error:
        raise MarketplaceAPIError(
            f"Location-token exchange failed ({response.status_code})."
        )
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise MarketplaceAPIError("Location-token response is missing access_token.")
    payload.setdefault("companyId", company_id)
    payload.setdefault("locationId", location_id)
    return payload


async def create_wallet_charge(
    *,
    access_token: str,
    app_id: str,
    meter_id: str,
    event_id: str,
    location_id: str,
    company_id: str,
    description: str,
    units: int,
    user_id: str = "",
    price: float | None = None,
    event_time: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "appId": app_id,
        "meterId": meter_id,
        "eventId": event_id,
        "locationId": location_id,
        "companyId": company_id,
        "description": description,
        "units": units,
    }
    if user_id:
        body["userId"] = user_id
    if price is not None:
        body["price"] = price
    if event_time:
        body["eventTime"] = event_time
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/marketplace/billing/charges",
            headers={**_headers(access_token), "Content-Type": "application/json"},
            json=body,
        )
    if response.is_error:
        raise MarketplaceAPIError(
            f"Wallet charge failed ({response.status_code})."
        )
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("success"):
        raise MarketplaceAPIError("Wallet charge was not accepted.")
    return payload

