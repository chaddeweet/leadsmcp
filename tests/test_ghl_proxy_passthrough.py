"""End-to-end proxy plumbing tests.

Proves that arguments sent to a namespaced, proxied ``ghl_execute_operation`` reach the
backend unchanged (no double-wrapping introduced by the FastMCP proxy or the mount), and
that the allowlist middleware does not block the v2 catalog when compatibility mode is on.
"""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP
from fastmcp.server import create_proxy

from ghl_tools import GHLToolAllowlistMiddleware, load_allowlist_config


def _fake_ghl_backend() -> FastMCP:
    backend = FastMCP(name="fake-ghl")

    @backend.tool
    def execute_operation(operation: str, params: dict | None = None) -> dict:
        return {"operation": operation, "params": params}

    @backend.tool
    def describe_operation(operation: str) -> dict:
        return {"operation": operation, "schema": {"type": "object"}}

    return backend


def _mount_proxy(*, with_allowlist: bool) -> FastMCP:
    proxy = create_proxy(Client(_fake_ghl_backend()), name="GHL Proxy")
    root = FastMCP(name="root")
    root.mount(proxy, namespace="ghl")
    if with_allowlist:
        root.add_middleware(GHLToolAllowlistMiddleware(config=load_allowlist_config(env={})))
    return root


@pytest.mark.asyncio
async def test_execute_operation_arguments_pass_through_unchanged():
    root = _mount_proxy(with_allowlist=False)
    payload = {
        "operation": "contacts_create-contact",
        "params": {
            "name": "Jane Doe",
            "phone": "+15551234567",
            "address1": "1 Main St",
            "city": "Austin",
            "state": "TX",
            "postalCode": "78701",
            "website": "https://example.com",
            "timezone": "America/Chicago",
            "tags": ["outscraper"],
            "source": "leadsmcp",
            "companyName": "Example LLC",
        },
    }
    async with Client(root) as c:
        res = await c.call_tool("ghl_execute_operation", payload)

    # Exactly what was sent — no extra nesting/wrapping around operation or params.
    assert res.structured_content == payload


@pytest.mark.asyncio
async def test_execute_operation_reachable_with_allowlist_enabled():
    root = _mount_proxy(with_allowlist=True)
    async with Client(root) as c:
        names = {t.name for t in await c.list_tools()}
        assert "ghl_execute_operation" in names
        assert "ghl_describe_operation" in names
        res = await c.call_tool(
            "ghl_execute_operation",
            {"operation": "contacts_create-contact", "params": {"name": "Jane"}},
        )
    assert res.structured_content["operation"] == "contacts_create-contact"
