#!/usr/bin/env python3
"""
LeadsMCP smoke test.

Checks:
1) HTTP health endpoint
2) MCP tool discovery (with optional x-mcp-secret)
3) Stripe dry-run via stripe_estimate_qualified_lead_export_cost
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

REQUIRED_TOOLS = {
    "outscraper_google_maps_search",
    "outscraper_email_validator",
    "stripe_analyze_qualified_lead_export",
    "stripe_plan_qualified_lead_export_billing",
    "stripe_estimate_qualified_lead_export_cost",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run smoke checks against a LeadsMCP server.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("MCP_SERVER_BASE_URL", "http://localhost:8000"),
        help="Base server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--mcp-secret",
        default=os.getenv("MCP_SECRET", ""),
        help="MCP secret header value (defaults to MCP_SECRET env var if set).",
    )
    parser.add_argument(
        "--qualified-leads",
        type=int,
        default=7,
        help="Qualified lead count used for stripe estimate dry-run (default: 7).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds (default: 15).",
    )
    return parser.parse_args()


def _extract_json_payload(call_result: Any) -> dict[str, Any]:
    content = getattr(call_result, "content", None)
    if not isinstance(content, list):
        raise RuntimeError("Tool call did not return a content list.")

    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Tool response was not valid JSON: {text}") from exc
            if not isinstance(parsed, dict):
                raise RuntimeError("Tool JSON response was not an object.")
            return parsed

    raise RuntimeError("Tool response did not include text content.")


async def _run() -> int:
    load_dotenv()
    args = _parse_args()

    base_url = args.base_url.rstrip("/")
    health_url = f"{base_url}/health"
    mcp_url = f"{base_url}/mcp"
    headers: dict[str, str] = {}
    if args.mcp_secret.strip():
        headers["x-mcp-secret"] = args.mcp_secret.strip()

    print(f"[1/3] Checking health endpoint: {health_url}")
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        health_response = await client.get(health_url)
    health_response.raise_for_status()
    health_payload = health_response.json()
    if health_payload.get("status") != "healthy":
        raise RuntimeError(f"Health payload not healthy: {health_payload}")
    print("  PASS health")

    print(f"[2/3] Listing tools via MCP: {mcp_url}")
    http_client = create_mcp_http_client(headers=headers)
    async with http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as transport:
            read_stream, write_stream, _ = transport
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools_response = await session.list_tools()
                tool_names = {tool.name for tool in tools_response.tools}
                missing = sorted(REQUIRED_TOOLS - tool_names)
                if missing:
                    raise RuntimeError(
                        "Missing expected tools: " + ", ".join(missing)
                    )
                print(f"  PASS list_tools ({len(tool_names)} tools exposed)")

                print("[3/3] Running Stripe dry-run tool")
                call_result = await session.call_tool(
                    "stripe_estimate_qualified_lead_export_cost",
                    arguments={"qualified_leads": args.qualified_leads},
                )
                payload = _extract_json_payload(call_result)
                estimate = payload.get("estimated_total_usd")
                if estimate is None:
                    raise RuntimeError(f"Missing estimate in tool response: {payload}")
                print(
                    f"  PASS stripe dry-run (qualified_leads={args.qualified_leads}, "
                    f"estimated_total_usd={estimate})"
                )

    print("SMOKE TEST PASSED")
    return 0


def main() -> int:
    try:
        return asyncio.run(_run())
    except httpx.HTTPStatusError as exc:
        print(
            f"SMOKE TEST FAILED: HTTP {exc.response.status_code} at {exc.request.url}",
            file=sys.stderr,
        )
        try:
            print(exc.response.text, file=sys.stderr)
        except Exception:
            pass
        return 1
    except Exception as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
