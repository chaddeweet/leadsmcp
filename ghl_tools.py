"""GoHighLevel proxied-tool allowlist and canonical-name handling.

The GHL native MCP endpoint (``https://services.leadconnectorhq.com/mcp/``) exposes
a large tool surface spanning contacts, opportunities, conversations, locations,
calendars, payments, forms, social planner, email builder and blogs. When proxied
and mounted under the ``ghl`` namespace every one of those tools is re-exported as
``ghl_<group>_<action>`` (for example ``ghl_contacts_create-contact``), which is far
more than the LeadsMCP lead/contact workflow needs.

This module provides a small FastMCP middleware that:

  * filters the proxied ``ghl_*`` tools down to a configurable allowlist so only the
    tools that matter to the lead/contact workflow are discoverable and callable, and
  * rewrites well-known non-canonical aliases (e.g. ``ghl_create_contact``) to the
    canonical GHL name (``ghl_contacts_create-contact``) so a client that guesses the
    name still reaches the right tool.

Non-``ghl_`` tools (outscraper_*, stripe_*) are never touched.

Configuration (all optional, read from the environment):

  GHL_TOOL_ALLOWLIST_DISABLED
      Set truthy to expose the full proxied GHL surface (no filtering). Useful for
      debugging what the connected account actually offers.

  GHL_ENABLED_TOOL_GROUPS
      Comma-separated GHL tool groups to keep, matched against the ``<group>`` segment
      of ``ghl_<group>_...``. Defaults to the workflow-relevant groups
      (contacts, opportunities, conversations, locations).

  GHL_ENABLED_TOOLS
      Comma-separated explicit tool names to additionally keep. Names may be given with
      or without the ``ghl_`` prefix and with either hyphens or underscores in the
      action segment; they are normalised before matching. Use this to re-enable a
      single tool from an otherwise-disabled group.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools.tool import Tool

GHL_PREFIX = "ghl_"

# Tool groups that the documented LeadsMCP workflow actually uses:
#   contacts      → create/upsert/update/get contacts, tags, tasks (the CRM handoff)
#   opportunities → pipelines + opportunity records tied to exported leads
#   conversations → follow-up messaging after a lead is imported
#   locations     → custom-field discovery needed for field mapping
DEFAULT_ENABLED_GROUPS = ("contacts", "opportunities", "conversations", "locations")

# Contact write tools are the core of the export step and must never be filtered out
# just because a group list was mis-configured. These are always kept.
ALWAYS_ENABLED_TOOLS = (
    "ghl_contacts_create-contact",
    "ghl_contacts_upsert-contact",
)

# HighLevel MCP v2 exposes a compact catalog of unified tools instead of one tool per
# operation. Their names have no "<group>_" segment that the allowlist group filter can
# match (e.g. ``ghl_execute_operation`` parses to group "execute"), so plain group
# filtering would silently drop the entire v2 surface — including discovery and
# execution — the moment compatibility mode is switched on. These entrypoints gate access
# at the *operation* level upstream (subject to the connected token's scopes), so the
# tool-level allowlist must never hide them regardless of the configured groups.
V2_CATALOG_TOOLS = (
    "ghl_search",
    "ghl_fetch",
    "ghl_search_operations",
    "ghl_describe_operation",
    "ghl_execute_operation",
)

# Non-canonical names a client might guess, mapped to the canonical GHL tool name.
# Keys are given in "loose" form (see _loose): all separators after ``ghl_`` become
# hyphens, so ``ghl_create_contact`` and ``ghl_create-contact`` match the same entry.
_CANONICAL_ALIASES = {
    "ghl_create-contact": "ghl_contacts_create-contact",
    "ghl_contact-create": "ghl_contacts_create-contact",
    "ghl_contacts-create": "ghl_contacts_create-contact",
    "ghl_create-contacts": "ghl_contacts_create-contact",
    "ghl_upsert-contact": "ghl_contacts_upsert-contact",
    "ghl_contacts-upsert": "ghl_contacts_upsert-contact",
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize(name: str) -> str:
    """Lower-case and convert underscores in the action segment to hyphens.

    GHL uses hyphenated actions (``contacts_create-contact``); clients sometimes send
    ``contacts_create_contact``. We normalise the action part (everything after the
    ``ghl_<group>_`` boundary) so both spellings resolve to the same canonical name.
    """
    name = name.strip().lower()
    if not name.startswith(GHL_PREFIX):
        return name
    body = name[len(GHL_PREFIX):]
    group, sep, action = body.partition("_")
    if not sep:
        return name
    return f"{GHL_PREFIX}{group}_{action.replace('_', '-')}"


def _loose(name: str) -> str:
    """Collapse all separators after ``ghl_`` to hyphens for alias matching.

    ``ghl_create_contact`` and ``ghl_create-contact`` both map to ``ghl_create-contact``.
    """
    name = name.strip().lower()
    if not name.startswith(GHL_PREFIX):
        return name
    return GHL_PREFIX + name[len(GHL_PREFIX):].replace("_", "-")


def _group_of(name: str) -> str:
    body = name[len(GHL_PREFIX):] if name.startswith(GHL_PREFIX) else name
    return body.partition("_")[0]


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def load_allowlist_config(env: dict[str, str] | None = None) -> dict:
    """Build the effective allowlist configuration from the environment."""
    getter = (env or os.environ).get

    enabled_groups = _split_csv(getter("GHL_ENABLED_TOOL_GROUPS"))
    if not enabled_groups:
        enabled_groups = list(DEFAULT_ENABLED_GROUPS)

    explicit = {_normalize(n if n.startswith(GHL_PREFIX) else GHL_PREFIX + n)
                for n in _split_csv(getter("GHL_ENABLED_TOOLS"))}
    explicit.update(_normalize(n) for n in ALWAYS_ENABLED_TOOLS)

    return {
        "disabled": _truthy(getter("GHL_TOOL_ALLOWLIST_DISABLED")),
        "groups": {g.lower() for g in enabled_groups},
        "explicit": explicit,
        "aliases": dict(_CANONICAL_ALIASES),
    }


def is_tool_allowed(name: str, config: dict) -> bool:
    """Return True if a fully-namespaced tool name should be exposed/callable."""
    if not name.startswith(GHL_PREFIX):
        return True  # never touch outscraper_/stripe_/local tools
    if config["disabled"]:
        return True
    normalized = _normalize(name)
    if normalized in V2_CATALOG_TOOLS:
        return True
    if normalized in config["explicit"]:
        return True
    return _group_of(normalized) in config["groups"]


class GHLToolAllowlistMiddleware(Middleware):
    """Filter proxied GHL tools to an allowlist and canonicalise call names."""

    def __init__(self, config: dict | None = None):
        self.config = config or load_allowlist_config()

    async def on_list_tools(self, context: MiddlewareContext, call_next) -> Sequence[Tool]:
        tools = await call_next(context)
        return [t for t in tools if is_tool_allowed(t.name, self.config)]

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        name = context.message.name
        if name.startswith(GHL_PREFIX):
            canonical = self.config["aliases"].get(_loose(name))
            if canonical and canonical != name:
                context.message.name = canonical
                name = canonical
            if not is_tool_allowed(name, self.config):
                enabled = ", ".join(sorted(self.config["groups"])) or "(none)"
                raise ValueError(
                    f"GHL tool '{name}' is disabled by the LeadsMCP allowlist. "
                    f"Enabled groups: {enabled}. Add it via GHL_ENABLED_TOOLS or "
                    f"GHL_ENABLED_TOOL_GROUPS, or set GHL_TOOL_ALLOWLIST_DISABLED=true."
                )
        return await call_next(context)
