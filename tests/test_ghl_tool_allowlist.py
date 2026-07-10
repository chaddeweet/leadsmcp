"""Tests for the GHL proxied-tool allowlist and canonical-name handling.

Covers the pure allowlist predicate plus an end-to-end proxy+mount+middleware run
against a representative fake GHL backend that mirrors the native GHL tool surface
(contacts, opportunities, conversations, locations, calendars, payments, forms,
social planner, email builder, blogs).
"""
import pytest
from fastmcp import Client, FastMCP
from fastmcp.server import create_proxy

from ghl_tools import (
    ALWAYS_ENABLED_TOOLS,
    DEFAULT_ENABLED_GROUPS,
    GHLToolAllowlistMiddleware,
    is_tool_allowed,
    load_allowlist_config,
)

# A representative slice of the native GHL MCP surface, named the way GHL names them
# (``<group>_<hyphenated-action>``). Mounted under the ``ghl`` namespace below.
FAKE_GHL_TOOLS = [
    # contacts (workflow-relevant)
    "contacts_create-contact",
    "contacts_upsert-contact",
    "contacts_update-contact",
    "contacts_get-contact",
    "contacts_get-contacts",
    "contacts_add-tags",
    "contacts_remove-tags",
    "contacts_get-all-tasks",
    # opportunities (workflow-relevant)
    "opportunities_search-opportunity",
    "opportunities_get-opportunity",
    "opportunities_update-opportunity",
    "opportunities_get-pipelines",
    # conversations (workflow-relevant)
    "conversations_search-conversation",
    "conversations_send-a-new-message",
    # locations (workflow-relevant)
    "locations_get-location",
    "locations_get-custom-fields",
    # clearly-irrelevant groups that should be pruned by default
    "calendars_get-calendar-events",
    "calendars_get-appointment-notes",
    "payments_list-transactions",
    "payments_get-order-by-id",
    "forms_get-forms",
    "socialplanner_get-posts",
    "socialplanner_create-post",
    "emails_get-templates",
    "blogs_get-posts",
    "blogs_create-post",
]

GHL_GROUPS_PRUNED_BY_DEFAULT = {
    "calendars", "payments", "forms", "socialplanner", "emails", "blogs",
}


def build_orchestrator(config=None) -> FastMCP:
    """Build an orchestrator mounting a fake GHL proxy + the allowlist middleware."""
    backend = FastMCP(name="Fake GHL")
    for tool_name in FAKE_GHL_TOOLS:
        def _make(n):
            def _fn(firstName: str = "") -> str:
                return f"called {n}"
            return _fn
        backend.tool(name=tool_name)(_make(tool_name))

    # A non-GHL tool must always survive filtering.
    orch = FastMCP(name="orch")

    @orch.tool(name="outscraper_google_maps_search")
    def _search() -> str:
        return "search"

    orch.mount(create_proxy(backend, name="GHL Proxy"), namespace="ghl")
    orch.add_middleware(GHLToolAllowlistMiddleware(config))
    return orch


async def list_names(orch: FastMCP) -> set[str]:
    async with Client(orch) as client:
        return {t.name for t in await client.list_tools()}


# ── Pure predicate tests ────────────────────────────────────────────────────

def test_default_config_keeps_workflow_groups():
    config = load_allowlist_config(env={})
    assert config["groups"] == set(DEFAULT_ENABLED_GROUPS)
    assert is_tool_allowed("ghl_contacts_create-contact", config)
    assert is_tool_allowed("ghl_opportunities_get-pipelines", config)
    assert is_tool_allowed("ghl_locations_get-custom-fields", config)


def test_default_config_prunes_irrelevant_groups():
    config = load_allowlist_config(env={})
    assert not is_tool_allowed("ghl_blogs_create-post", config)
    assert not is_tool_allowed("ghl_socialplanner_create-post", config)
    assert not is_tool_allowed("ghl_calendars_get-calendar-events", config)


def test_non_ghl_tools_are_never_filtered():
    config = load_allowlist_config(env={})
    assert is_tool_allowed("outscraper_google_maps_search", config)
    assert is_tool_allowed("stripe_record_qualified_lead_export", config)


def test_create_contact_always_enabled_even_without_contacts_group():
    config = load_allowlist_config(env={"GHL_ENABLED_TOOL_GROUPS": "opportunities"})
    assert "contacts" not in config["groups"]
    for tool in ALWAYS_ENABLED_TOOLS:
        assert is_tool_allowed(tool, config)


def test_explicit_tool_reenables_single_tool():
    config = load_allowlist_config(env={
        "GHL_ENABLED_TOOL_GROUPS": "contacts",
        "GHL_ENABLED_TOOLS": "payments_list-transactions",
    })
    assert is_tool_allowed("ghl_payments_list-transactions", config)
    assert not is_tool_allowed("ghl_payments_get-order-by-id", config)


def test_allowlist_disabled_exposes_everything():
    config = load_allowlist_config(env={"GHL_TOOL_ALLOWLIST_DISABLED": "true"})
    assert is_tool_allowed("ghl_blogs_create-post", config)


def test_underscore_action_normalizes_to_hyphen():
    config = load_allowlist_config(env={})
    # client sends underscore spelling; predicate should still match the group
    assert is_tool_allowed("ghl_contacts_create_contact", config)


# ── End-to-end proxy + mount + middleware tests ─────────────────────────────

@pytest.mark.asyncio
async def test_before_after_counts_and_create_contact_present():
    # Before: no filtering → full proxied surface + the local outscraper tool.
    all_names = await list_names(build_orchestrator(
        load_allowlist_config(env={"GHL_TOOL_ALLOWLIST_DISABLED": "true"})
    ))
    ghl_before = {n for n in all_names if n.startswith("ghl_")}
    assert len(ghl_before) == len(FAKE_GHL_TOOLS)
    assert "ghl_contacts_create-contact" in ghl_before

    # After: default allowlist prunes the irrelevant groups.
    kept = await list_names(build_orchestrator(load_allowlist_config(env={})))
    ghl_after = {n for n in kept if n.startswith("ghl_")}

    # create-contact survives and is discoverable under its canonical name.
    assert "ghl_contacts_create-contact" in ghl_after
    assert "ghl_contacts_upsert-contact" in ghl_after
    # non-GHL tool survives.
    assert "outscraper_google_maps_search" in kept
    # every pruned group is gone.
    for name in ghl_after:
        group = name[len("ghl_"):].split("_", 1)[0]
        assert group not in GHL_GROUPS_PRUNED_BY_DEFAULT
    assert len(ghl_after) < len(ghl_before)


@pytest.mark.asyncio
async def test_create_contact_callable_via_canonical_name():
    orch = build_orchestrator(load_allowlist_config(env={}))
    async with Client(orch) as client:
        result = await client.call_tool(
            "ghl_contacts_create-contact", {"firstName": "Jane"}
        )
        assert "contacts_create-contact" in result.content[0].text


@pytest.mark.asyncio
async def test_alias_is_rewritten_to_canonical():
    orch = build_orchestrator(load_allowlist_config(env={}))
    async with Client(orch) as client:
        result = await client.call_tool("ghl_create_contact", {"firstName": "Al"})
        assert "contacts_create-contact" in result.content[0].text


@pytest.mark.asyncio
async def test_disabled_tool_call_is_blocked():
    orch = build_orchestrator(load_allowlist_config(env={}))
    async with Client(orch) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("ghl_blogs_create-post", {})
        assert "disabled" in str(excinfo.value).lower()
