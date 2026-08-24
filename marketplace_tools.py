"""Marketplace-safe tool catalog for the public LeadsMCP endpoint.

The runtime still mounts the internal Outscraper, billing, disposable-inbox, and
LeadConnector MCP servers so existing implementations can be reused. In
``marketplace`` mode this middleware is the product boundary: discovery exposes
only the approved outcome-oriented names, direct calls to internal names are
denied, and CRM writes require explicit confirmation.

Set ``LEADSMCP_MODE=developer`` only in a controlled development deployment to
restore the underlying catalog.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools.function_tool import FunctionTool
from fastmcp.tools.tool import Tool


MARKETPLACE_MODE = "marketplace"
DEVELOPER_MODE = "developer"

# Public name -> mounted implementation name.
PUBLIC_TOOL_TARGETS = {
    "lead_search": "outscraper_google_maps_search",
    "lead_fetch": "outscraper_get_request_results",
    "lead_enrich": "outscraper_emails_and_contacts",
    "lead_validate": "outscraper_email_validator",
    "crm_find_contact": "ghl_search",
    "crm_import_contact": "ghl_contacts_upsert_contact",
    "crm_list_pipelines": "ghl_execute_operation",
    "crm_create_opportunity": "ghl_execute_operation",
    "operation_status": "outscraper_get_request_results",
}

WRITE_TOOLS = frozenset({"crm_import_contact", "crm_create_opportunity"})

PUBLIC_TOOL_DESCRIPTIONS = {
    "lead_search": "Search for businesses and prospective leads by category and geography.",
    "lead_fetch": "Fetch the completed results for a lead-search request.",
    "lead_enrich": "Enrich company domains with business contact details.",
    "lead_validate": "Validate lead email addresses before CRM import.",
    "crm_find_contact": "Find an existing contact in the connected CRM before importing a lead.",
    "crm_import_contact": (
        "Create or update a CRM contact. This write is blocked unless confirm=true. "
        "Use a deterministic external identifier or email/phone match to prevent duplicates."
    ),
    "crm_list_pipelines": "List opportunity pipelines available to the connected business account.",
    "crm_create_opportunity": (
        "Create an opportunity for an existing CRM contact. This write is blocked "
        "unless confirm=true and should use an idempotency key."
    ),
    "operation_status": "Check the status of a long-running lead operation.",
}


def _crm_find_contact_template(query: str) -> dict[str, Any]:
    raise RuntimeError("An authenticated CRM installation is required.")


def _crm_import_contact_template(
    operation_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    raise RuntimeError("An authenticated CRM installation is required.")


def _crm_list_pipelines_template(
    operation_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    raise RuntimeError("An authenticated CRM installation is required.")


def _crm_create_opportunity_template(
    operation_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    raise RuntimeError("An authenticated CRM installation is required.")


CRM_TOOL_TEMPLATES = {
    "crm_find_contact": FunctionTool.from_function(
        _crm_find_contact_template,
        name="crm_find_contact",
    ),
    "crm_import_contact": FunctionTool.from_function(
        _crm_import_contact_template,
        name="crm_import_contact",
    ),
    "crm_list_pipelines": FunctionTool.from_function(
        _crm_list_pipelines_template,
        name="crm_list_pipelines",
    ),
    "crm_create_opportunity": FunctionTool.from_function(
        _crm_create_opportunity_template,
        name="crm_create_opportunity",
    ),
}


def load_marketplace_mode(env: dict[str, str] | None = None) -> str:
    """Return the validated runtime mode, defaulting closed to Marketplace."""
    value = (env or os.environ).get("LEADSMCP_MODE", MARKETPLACE_MODE)
    mode = (value or MARKETPLACE_MODE).strip().lower()
    if mode not in {MARKETPLACE_MODE, DEVELOPER_MODE}:
        raise ValueError(
            "LEADSMCP_MODE must be 'marketplace' or 'developer'; "
            f"received {value!r}."
        )
    return mode


def _public_parameters(tool: Tool, public_name: str) -> dict[str, Any]:
    parameters = deepcopy(tool.parameters)
    if public_name not in WRITE_TOOLS:
        return parameters

    properties = parameters.setdefault("properties", {})
    properties["confirm"] = {
        "type": "boolean",
        "description": (
            "Explicit user confirmation for this CRM write. Must be true for "
            "the operation to run."
        ),
    }
    required = list(parameters.get("required", []))
    if "confirm" not in required:
        required.append("confirm")
    parameters["required"] = required
    return parameters


class MarketplaceToolCatalogMiddleware(Middleware):
    """Expose the nine-tool Marketplace contract and deny internal tool calls."""

    def __init__(self, mode: str | None = None):
        self.mode = mode or load_marketplace_mode()
        self._available_targets: set[str] = set()
        if self.mode not in {MARKETPLACE_MODE, DEVELOPER_MODE}:
            raise ValueError(f"Unsupported LeadsMCP mode: {self.mode!r}")

    async def on_list_tools(
        self, context: MiddlewareContext, call_next
    ) -> Sequence[Tool]:
        tools = await call_next(context)
        if self.mode == DEVELOPER_MODE:
            return tools

        by_name = {tool.name: tool for tool in tools}
        self._available_targets = set(by_name)
        public_tools: list[Tool] = []
        for public_name, target_name in PUBLIC_TOOL_TARGETS.items():
            target = by_name.get(target_name)
            if target is None:
                target = CRM_TOOL_TEMPLATES.get(public_name)
            if target is None:
                continue
            public_tools.append(
                target.model_copy(
                    update={
                        "name": public_name,
                        "title": public_name.replace("_", " ").title(),
                        "description": PUBLIC_TOOL_DESCRIPTIONS[public_name],
                        "parameters": _public_parameters(target, public_name),
                    },
                    # FunctionTool contains immutable mappingproxy metadata that
                    # cannot be pickled by Pydantic's deep-copy path. The
                    # parameter schema above is already deep-copied explicitly.
                    deep=False,
                )
            )
        return public_tools

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        if self.mode == DEVELOPER_MODE:
            return await call_next(context)

        public_name = context.message.name
        target_name = PUBLIC_TOOL_TARGETS.get(public_name)
        if target_name is None:
            raise ValueError(
                f"Tool '{public_name}' is not available in the LeadsMCP "
                "Marketplace catalog."
            )
        arguments = dict(context.message.arguments or {})
        if public_name in WRITE_TOOLS:
            if arguments.get("confirm") is not True:
                raise ValueError(
                    f"Tool '{public_name}' requires confirm=true before a CRM write."
                )
            arguments.pop("confirm", None)

        if (
            target_name.startswith("ghl_")
            and target_name not in self._available_targets
        ):
            raise ValueError(
                f"Tool '{public_name}' requires an authenticated CRM "
                "installation for this request."
            )

        context.message.name = target_name
        context.message.arguments = arguments
        return await call_next(context)
