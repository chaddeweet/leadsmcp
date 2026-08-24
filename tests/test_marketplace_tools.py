from types import SimpleNamespace

import pytest
from fastmcp.tools.function_tool import FunctionTool

from marketplace_tools import (
    DEVELOPER_MODE,
    MARKETPLACE_MODE,
    PUBLIC_TOOL_TARGETS,
    MarketplaceToolCatalogMiddleware,
    load_marketplace_mode,
)


class FakeTool:
    def __init__(self, name, parameters=None, **values):
        self.name = name
        self.parameters = parameters or {
            "type": "object",
            "properties": {"operation": {"type": "string"}},
            "required": ["operation"],
        }
        self.values = values

    def model_copy(self, update=None, deep=False):
        values = {
            "name": self.name,
            "parameters": self.parameters,
            **self.values,
            **(update or {}),
        }
        return FakeTool(**values)


def _context(name, arguments=None):
    return SimpleNamespace(
        message=SimpleNamespace(name=name, arguments=arguments or {})
    )


def test_mode_defaults_closed_to_marketplace():
    assert load_marketplace_mode({}) == MARKETPLACE_MODE
    assert load_marketplace_mode({"LEADSMCP_MODE": "developer"}) == DEVELOPER_MODE


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError, match="marketplace.*developer"):
        load_marketplace_mode({"LEADSMCP_MODE": "public"})


@pytest.mark.asyncio
async def test_marketplace_discovery_exposes_only_nine_public_names():
    internal = [FakeTool(name) for name in set(PUBLIC_TOOL_TARGETS.values())]
    internal.append(FakeTool("stripe_create_meter_event"))
    middleware = MarketplaceToolCatalogMiddleware(MARKETPLACE_MODE)

    tools = await middleware.on_list_tools(None, lambda _: _return(internal))

    assert [tool.name for tool in tools] == list(PUBLIC_TOOL_TARGETS)
    assert len(tools) == 9
    assert "stripe_create_meter_event" not in {tool.name for tool in tools}


@pytest.mark.asyncio
async def test_marketplace_discovery_copies_real_function_tool():
    def google_maps_search(query: str) -> dict:
        return {"query": query}

    internal = FunctionTool.from_function(
        google_maps_search,
        name="outscraper_google_maps_search",
    )
    middleware = MarketplaceToolCatalogMiddleware(MARKETPLACE_MODE)

    tools = await middleware.on_list_tools(None, lambda _: _return([internal]))

    names = [tool.name for tool in tools]
    assert "lead_search" in names
    assert {
        "crm_find_contact",
        "crm_import_contact",
        "crm_list_pipelines",
        "crm_create_opportunity",
    }.issubset(names)
    lead_search = next(tool for tool in tools if tool.name == "lead_search")
    assert lead_search.parameters["properties"]["query"]["type"] == "string"


@pytest.mark.asyncio
async def test_unbound_crm_tool_returns_clear_authentication_error():
    middleware = MarketplaceToolCatalogMiddleware(MARKETPLACE_MODE)
    context = _context("crm_find_contact", {"query": "test@example.com"})

    with pytest.raises(ValueError, match="authenticated CRM installation"):
        await middleware.on_call_tool(context, _echo_call)


@pytest.mark.asyncio
async def test_crm_write_requires_confirmation_and_strips_guard_argument():
    middleware = MarketplaceToolCatalogMiddleware(MARKETPLACE_MODE)
    denied = _context("crm_import_contact", {"email": "test@example.com"})
    with pytest.raises(ValueError, match="confirm=true"):
        await middleware.on_call_tool(denied, _echo_call)

    allowed = _context(
        "crm_import_contact",
        {"email": "test@example.com", "confirm": True},
    )
    middleware._available_targets.add("ghl_contacts_upsert_contact")
    result = await middleware.on_call_tool(allowed, _echo_call)
    assert result.name == "ghl_contacts_upsert_contact"
    assert result.arguments == {"email": "test@example.com"}


@pytest.mark.asyncio
async def test_internal_tool_name_is_denied_in_marketplace_mode():
    middleware = MarketplaceToolCatalogMiddleware(MARKETPLACE_MODE)
    context = _context("outscraper_google_maps_search")
    with pytest.raises(ValueError, match="not available"):
        await middleware.on_call_tool(context, _echo_call)


@pytest.mark.asyncio
async def test_developer_mode_preserves_internal_catalog():
    internal = [FakeTool("stripe_create_meter_event")]
    middleware = MarketplaceToolCatalogMiddleware(DEVELOPER_MODE)
    tools = await middleware.on_list_tools(None, lambda _: _return(internal))
    assert tools is internal


async def _return(value):
    return value


async def _echo_call(context):
    return context.message
