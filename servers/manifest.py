"""Build a tool manifest from the actually-registered MCP tools.

The manifest is generated directly from the live ``FastMCP`` sub-servers so it
cannot drift from the real tool surface. Tool names are namespaced exactly as
``main.py`` mounts them (``outscraper_*`` / ``stripe_*`` / ``tempmail_*``) so the manifest matches
what an MCP client sees on the orchestrator endpoint.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from servers.outscraper_server import mcp as outscraper_mcp
from servers.stripe_server import mcp as stripe_mcp
from servers.tempmail_server import mcp as tempmail_mcp

MANIFEST_VERSION = 1

# (namespace, FastMCP server) — must mirror the orchestrator.mount(...) calls.
MOUNTED_SERVERS = [
    ("outscraper", outscraper_mcp),
    ("stripe", stripe_mcp),
    ("tempmail", tempmail_mcp),
]


async def _collect_server_tools(namespace: str, server: Any) -> list[dict[str, Any]]:
    tools = await server._list_tools()
    entries: list[dict[str, Any]] = []
    for tool in sorted(tools, key=lambda t: t.name):
        entries.append(
            {
                "name": f"{namespace}_{tool.name}",
                "server": namespace,
                "local_name": tool.name,
                "description": (tool.description or "").strip(),
                "input_schema": tool.parameters or {"type": "object"},
                "output_schema": tool.output_schema or {"type": "object"},
            }
        )
    return entries


async def build_manifest_async() -> dict[str, Any]:
    tools: list[dict[str, Any]] = []
    for namespace, server in MOUNTED_SERVERS:
        tools.extend(await _collect_server_tools(namespace, server))
    tools.sort(key=lambda entry: entry["name"])
    server_names = ", ".join(f"servers.{ns}_server" for ns, _ in MOUNTED_SERVERS)
    return {
        "manifest_version": MANIFEST_VERSION,
        "generated_from": server_names,
        "tool_count": len(tools),
        "tools": tools,
    }


def build_manifest() -> dict[str, Any]:
    return asyncio.run(build_manifest_async())


def manifest_json(manifest: dict[str, Any] | None = None) -> str:
    if manifest is None:
        manifest = build_manifest()
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def manifest_path() -> Path:
    return Path(__file__).resolve().parent.parent / "tools.json"


def write_manifest() -> Path:
    path = manifest_path()
    path.write_text(manifest_json(), encoding="utf-8")
    return path
