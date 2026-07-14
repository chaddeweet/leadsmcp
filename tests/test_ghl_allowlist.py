"""Regression tests for the GHL tool allowlist middleware.

These lock in the fix for the v2 five-tool catalog being silently dropped when
compatibility mode (GHL_V2_TOOL_ALLOWLIST_ENABLED) is switched on, plus the existing
legacy-name and alias behaviour the middleware is responsible for.
"""

from __future__ import annotations

import pytest

from ghl_tools import (
    V2_CATALOG_TOOLS,
    GHLToolAllowlistMiddleware,
    is_tool_allowed,
    load_allowlist_config,
)


@pytest.fixture
def default_config():
    # Empty env => compatibility mode active with the default lead/contact groups.
    return load_allowlist_config(env={})


@pytest.mark.parametrize("tool", V2_CATALOG_TOOLS)
def test_v2_catalog_tools_survive_compatibility_mode(default_config, tool):
    # The v2 discovery/execution surface must remain callable even with the legacy
    # group allowlist enabled; otherwise create-contact can never be reached.
    assert is_tool_allowed(tool, default_config) is True


def test_execute_operation_specifically_allowed(default_config):
    assert is_tool_allowed("ghl_execute_operation", default_config) is True


def test_legacy_contact_write_tools_still_allowed(default_config):
    assert is_tool_allowed("ghl_contacts_create-contact", default_config) is True
    assert is_tool_allowed("ghl_contacts_upsert-contact", default_config) is True


def test_out_of_group_tool_filtered_in_compat_mode(default_config):
    # A tool in a group not on the default list is filtered (compat mode's whole point).
    assert is_tool_allowed("ghl_blogs_create-post", default_config) is False


def test_non_ghl_tools_never_filtered(default_config):
    assert is_tool_allowed("outscraper_google_maps_search", default_config) is True
    assert is_tool_allowed("stripe_ensure_customer_profile", default_config) is True


def test_disabled_flag_exposes_everything():
    config = load_allowlist_config(env={"GHL_TOOL_ALLOWLIST_DISABLED": "true"})
    assert is_tool_allowed("ghl_blogs_create-post", config) is True
    assert is_tool_allowed("ghl_execute_operation", config) is True


def test_explicit_tool_reenables_group():
    config = load_allowlist_config(env={"GHL_ENABLED_TOOLS": "blogs_create-post"})
    assert is_tool_allowed("ghl_blogs_create-post", config) is True


class _Msg:
    def __init__(self, name):
        self.name = name


class _Ctx:
    def __init__(self, name):
        self.message = _Msg(name)


@pytest.mark.asyncio
async def test_call_tool_canonicalises_alias(default_config):
    middleware = GHLToolAllowlistMiddleware(config=default_config)
    ctx = _Ctx("ghl_create_contact")  # loose/guessed name with underscore

    seen = {}

    async def call_next(context):
        seen["name"] = context.message.name
        return "ok"

    result = await middleware.on_call_tool(ctx, call_next)
    assert result == "ok"
    assert seen["name"] == "ghl_contacts_create-contact"


@pytest.mark.asyncio
async def test_call_tool_blocks_disabled_group(default_config):
    middleware = GHLToolAllowlistMiddleware(config=default_config)
    ctx = _Ctx("ghl_blogs_create-post")

    async def call_next(context):  # pragma: no cover - must not run
        raise AssertionError("blocked tool should not reach call_next")

    with pytest.raises(ValueError):
        await middleware.on_call_tool(ctx, call_next)


@pytest.mark.asyncio
async def test_call_tool_allows_execute_operation(default_config):
    middleware = GHLToolAllowlistMiddleware(config=default_config)
    ctx = _Ctx("ghl_execute_operation")

    async def call_next(context):
        return "executed"

    assert await middleware.on_call_tool(ctx, call_next) == "executed"


@pytest.mark.asyncio
async def test_list_tools_keeps_v2_catalog(default_config):
    middleware = GHLToolAllowlistMiddleware(config=default_config)

    class _Tool:
        def __init__(self, name):
            self.name = name

    tools = [
        _Tool("ghl_execute_operation"),
        _Tool("ghl_describe_operation"),
        _Tool("ghl_blogs_create-post"),
        _Tool("ghl_contacts_create-contact"),
        _Tool("outscraper_google_maps_search"),
    ]

    async def call_next(context):
        return tools

    kept = {t.name for t in await middleware.on_list_tools(object(), call_next)}
    assert "ghl_execute_operation" in kept
    assert "ghl_describe_operation" in kept
    assert "ghl_contacts_create-contact" in kept
    assert "outscraper_google_maps_search" in kept
    assert "ghl_blogs_create-post" not in kept
