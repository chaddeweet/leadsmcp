"""
MCP Orchestrator — Single cloud endpoint aggregating multiple services.

Services mounted:
  outscraper_*  →  Outscraper API (Google Maps, email/phone validation, enrichment)
  ghl_*         →  GoHighLevel native MCP (contacts, opportunities, pipelines)
  stripe_*      →  Stripe billing (qualified lead analysis, consent gating, metering)
  tempmail_*    →  TempMail.so (disposable inboxes for outreach signups/verification)

Start locally:   python3 main.py
MCP endpoint:    http://localhost:8000/mcp
Health check:    http://localhost:8000/health
"""
import asyncio
import base64
import contextlib
import datetime
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, AsyncIterator, cast
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from cryptography.fernet import Fernet
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP, Client
from fastmcp.exceptions import ToolError
from fastmcp.client.transports.http import StreamableHttpTransport
from fastmcp.server import create_proxy
from fastmcp.server.dependencies import get_http_headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.requests import Request

from servers.outscraper_server import mcp as outscraper_mcp
from servers.stripe_server import mcp as stripe_mcp
from servers.tempmail_server import mcp as tempmail_mcp
from ghl_tools import GHLToolAllowlistMiddleware
from marketplace_tools import (
    DEVELOPER_MODE,
    MarketplaceToolCatalogMiddleware,
    load_marketplace_mode,
)
from ghl_install_store import (
    get_installation,
    get_webhook_event,
    get_wallet_charge,
    install_store_backend,
    list_installations,
    mark_uninstalled,
    patch_installations,
    persist_install_record,
    record_webhook_event,
    supabase_configured as ghl_install_supabase_configured,
    upsert_wallet_charge,
    webhook_event_exists,
)
from ghl_marketplace import (
    MarketplaceAPIError,
    create_wallet_charge,
    exchange_location_token,
    get_installed_locations,
)
from ghl_webhooks import verify_ghl_signature, webhook_event_id
from ghl_contact_create import (
    ContactCreateError,
    build_create_contact_body,
    map_create_contact_response,
)

import connector_oauth

# Exact request paths that are always public (no x-mcp-secret required). The MCP
# protocol endpoint itself lives at the exact path "/mcp" and is deliberately not
# listed here, so it stays protected.
_PUBLIC_EXACT_PATHS = frozenset({
    "/",
    "/health",
    "/favicon.ico",
    "/support",
    "/support/",
    "/contact",
    "/contact/",
    "/app-install-successfully",
    "/app-install-successfully/",
    "/oauth/ghl/start",
    "/oauth/ghl/callback",
    "/leadsmcp/install",
    "/leadsmcp-install",
    "/leadsmcp-install/",
    "/webhooks/ghl",
})

# OAuth discovery / DCR / authorize / token endpoints. These must be reachable
# without an x-mcp-secret so ChatGPT and Perplexity can complete the OAuth flow.
_CONNECTOR_PUBLIC_PATHS = frozenset({
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
    "/.well-known/mcp.json",
    "/register",
    "/authorize",
    "/token",
    "/oauth/connector/authorize",
    "/oauth/connector/approve",
    "/oauth/connector/token",
})


def _is_public_path(path: str) -> bool:
    """True for public routes served without an x-mcp-secret header.

    The exact "/mcp" protocol endpoint is intentionally excluded so the MCP
    transport stays authenticated.
    """
    if path in _PUBLIC_EXACT_PATHS or path in _CONNECTOR_PUBLIC_PATHS:
        return True
    # OAuth discovery must stay public, including the RFC 8414/9728
    # path-suffixed variants (e.g. /.well-known/oauth-protected-resource/mcp)
    # that spec-2025-06-18 MCP clients such as Perplexity probe first.
    if path.startswith("/.well-known/") or path.startswith("/mcp/.well-known/"):
        return True
    return False


# Retired experimental UI/API paths. They have no handlers, but the auth gate
# would otherwise turn a request for them into a 401 instead of a clean 404.
# Let them bypass the secret check so routing resolves them to a clean 404. They
# expose no content: there is no handler to reach.
RETIRED_PATHS = frozenset({
    "/app/lead-search",
    "/app/lead-search/",
    "/app/mapbox-style.json",
    "/app/onboarding",
    "/app/onboarding/",
    "/marketplace/onboarding",
    "/marketplace/onboarding/",
    "/api/marketplace/user-context",
    "/api/marketplace/lead-search",
    "/api/marketplace/geocode",
    "/api/marketplace/llm-chat",
    "/api/onboarding-chat",
    "/mcp/app/pwa",
    "/mcp/app/pwa/",
    "/mcp/app/manifest.webmanifest",
    "/mcp/app/sw.js",
    "/mcp/app/icon-192.png",
    "/mcp/app/icon-512.png",
    "/mcp/app/mapbox-style.json",
})


def _html_shell(*, title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ --bg:#0b0c0e; --surface:#14161a; --border:#2a2d33; --text:#edf1f7; --muted:#9aa4b2; --accent:#4cf5d2; --accent2:#6e7cff; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter,ui-sans-serif,system-ui,sans-serif; background:radial-gradient(circle at top right, rgba(110,124,255,.18), transparent 28%), radial-gradient(circle at top left, rgba(76,245,210,.12), transparent 24%), var(--bg); color:var(--text); line-height:1.6; }}
    .wrap {{ max-width:1120px; margin:0 auto; padding:24px; }}
    nav {{ display:flex; justify-content:space-between; align-items:center; gap:16px; padding:8px 0 24px; }}
    .brand {{ font-weight:800; letter-spacing:-0.03em; text-decoration:none; color:var(--text); display:flex; align-items:center; gap:10px; }}
    .dot {{ width:10px; height:10px; border-radius:999px; background:var(--accent); box-shadow:0 0 20px var(--accent); }}
    .nav-links {{ display:flex; gap:12px; flex-wrap:wrap; }}
    .btn {{ display:inline-flex; align-items:center; justify-content:center; padding:11px 16px; border-radius:12px; border:1px solid var(--border); text-decoration:none; color:var(--text); background:rgba(255,255,255,.02); }}
    .btn.primary {{ background:var(--accent); color:#07110f; border-color:transparent; font-weight:700; }}
    .hero, .panel {{ background:rgba(20,22,26,.88); border:1px solid var(--border); border-radius:24px; padding:32px; box-shadow:0 20px 80px rgba(0,0,0,.25); }}
    h1,h2,h3 {{ line-height:1.05; letter-spacing:-0.03em; margin:0 0 12px; }}
    h1 {{ font-size:clamp(2.4rem,5vw,4.6rem); max-width:14ch; }}
    h2 {{ font-size:clamp(1.5rem,3vw,2.2rem); }}
    p {{ margin:0 0 14px; color:var(--muted); }}
    .grid {{ display:grid; gap:20px; }}
    .grid.cols-3 {{ grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); }}
    .grid.cols-2 {{ grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }}
    .card {{ background:rgba(255,255,255,.03); border:1px solid var(--border); border-radius:18px; padding:20px; }}
    .kicker {{ display:inline-block; margin-bottom:14px; color:var(--accent); font-weight:700; text-transform:uppercase; font-size:.78rem; letter-spacing:.08em; }}
    code, pre {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .stack > * + * {{ margin-top:18px; }}
    .checklist {{ display:grid; gap:10px; margin:0; padding:0; list-style:none; }}
    .checklist li {{ position:relative; padding-left:24px; color:var(--muted); }}
    .checklist li::before {{ content:"•"; position:absolute; left:0; top:0; color:var(--accent); font-weight:900; }}
    .stat-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; }}
    .stat {{ padding:16px 18px; border-radius:16px; border:1px solid var(--border); background:rgba(255,255,255,.03); }}
    .stat strong {{ display:block; font-size:1.8rem; line-height:1; letter-spacing:-0.04em; margin-bottom:6px; }}
    .quote {{ padding:22px; border-radius:20px; border:1px solid var(--border); background:linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02)); }}
    .quote p {{ color:var(--text); font-size:1.05rem; }}
    .section-head {{ max-width:64ch; }}
    .section-head p:last-child {{ margin-bottom:0; }}
    .footer {{ padding:30px 0 10px; color:var(--muted); font-size:.95rem; }}
    ul {{ margin:0; padding-left:20px; color:var(--muted); }}
    @media (max-width:720px) {{ .hero,.panel {{ padding:24px; }} nav {{ flex-direction:column; align-items:flex-start; }} }}
  </style>
</head>
<body>
  {body}
</body>
</html>"""


def _page_nav(base_url: str, github_url: str) -> str:
    return f"""<nav><a class="brand" href="{base_url}/"><span class="dot"></span><span>LeadsMCP</span></a><div class="nav-links"><a class="btn" href="{base_url}/support/">Support</a><a class="btn" href="{base_url}/contact/">Contact</a><a class="btn" href="{github_url}">GitHub</a></div></nav>"""


def build_landing_page(*, base_url: str, install_url: str, github_url: str, canonical_url: str) -> str:
    cta = install_url or f"{base_url}/oauth/ghl/start"
    body = f"""<div class="wrap stack">
{_page_nav(base_url, github_url)}
<section class="hero stack">
  <span class="kicker">MCP Lead Generation Software</span>
  <h1>Stop paying for stale lead databases your team barely uses</h1>
  <p>LeadsMCP is a live-search, enrichment, and CRM handoff engine built for the Model Context Protocol. It helps growth teams, agencies, and AI operators find real companies, preview structured lead data before export, and push clean records into GoHighLevel without juggling five disconnected tools.</p>
  <div class="nav-links">
    <a class="btn primary" href="{cta}">Start Your Free Preview</a>
    <a class="btn" href="{github_url}">View API and MCP Docs</a>
  </div>
  <div class="stat-row">
    <div class="stat"><strong>Live</strong><span>Search and enrichment instead of a static database snapshot.</span></div>
    <div class="stat"><strong>Preview-first</strong><span>Review the data before CRM sync or export actions happen.</span></div>
    <div class="stat"><strong>MCP-ready</strong><span>Give your AI workflows a consistent remote endpoint for lead operations.</span></div>
  </div>
</section>

<section class="panel stack">
  <div class="section-head">
    <span class="kicker">The Problem</span>
    <h2>The old lead generation stack leaks money, time, and trust</h2>
    <p>Most teams still buy credits or database seats first, then figure out later whether the contacts are current, whether the data is complete, and whether the records will even map cleanly into their CRM. That model worked when the goal was downloading CSV files. It breaks down when your team expects live data, workflow automation, and AI-assisted execution.</p>
    <p>LeadsMCP was built as the opposite of that experience. Instead of paying upfront for stale lists, you run live searches, enrich the results, review the output in a structured workspace, and decide what actually deserves to move into your pipeline.</p>
  </div>
  <div class="grid cols-3">
    <div class="card">
      <h3>Static data decays fast</h3>
      <p>Titles change, emails bounce, and local business details drift. By the time a static list reaches your SDR or operator, part of it is already losing value.</p>
    </div>
    <div class="card">
      <h3>Workflows get fragmented</h3>
      <p>Search lives in one tool, contact enrichment in another, validation in a third, and CRM handoff in a fourth. Every handoff adds friction and failure points.</p>
    </div>
    <div class="card">
      <h3>AI has no clean operating layer</h3>
      <p>Even when the data is useful, most lead stacks were not designed to be called cleanly by MCP-aware agents that need structured results and predictable actions.</p>
    </div>
  </div>
</section>

<section class="panel stack">
  <div class="section-head">
    <span class="kicker">The Shift</span>
    <h2>A long-form lead operations system built for modern teams</h2>
    <p>LeadsMCP is not just a search page and it is not just an API wrapper. It is a lead operations layer that combines live discovery, contact enrichment, review workflows, AI connectivity, and CRM delivery inside one consistent system.</p>
  </div>
  <div class="grid cols-2">
    <div class="card">
      <h3>Live discovery before commitment</h3>
      <p>Search Google Maps, websites, and research endpoints in real time. See what the system found before you decide what should move downstream.</p>
      <ul class="checklist">
        <li>Business discovery from live map and search signals</li>
        <li>Website-based contact extraction for domain-level research</li>
        <li>Structured results that can be reviewed in a workspace instead of raw dumps</li>
      </ul>
    </div>
    <div class="card">
      <h3>Operationally ready enrichment</h3>
      <p>LeadsMCP turns search results into cleaner, more actionable records so the output can actually be used by sales teams, agencies, or AI systems.</p>
      <ul class="checklist">
        <li>Email, phone, domain, and company signal capture</li>
        <li>Preview-first review workflows before CRM writes</li>
        <li>Consistent MCP access for downstream automation and AI use</li>
      </ul>
    </div>
  </div>
</section>

<section class="panel stack">
  <div class="section-head">
    <span class="kicker">How It Works</span>
    <h2>From search prompt to CRM-ready record</h2>
    <p>The system is designed to be simple for humans and structured for automation. Whether the request starts from a user inside GoHighLevel or an MCP-connected AI agent, the operational flow stays the same.</p>
  </div>
  <div class="grid cols-3">
    <div class="card">
      <h3>1. Search live sources</h3>
      <p>Run the search type that fits the job: Google Maps, website contact scraping, market research, validation, or profile discovery.</p>
    </div>
    <div class="card">
      <h3>2. Review before action</h3>
      <p>Inspect cards, raw payloads, and map views inside the workspace so the team can decide what is worth acting on.</p>
    </div>
    <div class="card">
      <h3>3. Push clean records</h3>
      <p>Hand qualified records into GoHighLevel with managed auth, tenant-aware routing, and a workflow surface that is actually automation friendly.</p>
    </div>
  </div>
</section>

<section class="panel stack">
  <div class="section-head">
    <span class="kicker">Why Teams Buy</span>
    <h2>What makes LeadsMCP different from a generic lead tool</h2>
    <p>This product is strongest when a team cares about more than “more rows in a spreadsheet.” It is designed for teams that want better control over how lead data is sourced, reviewed, and routed.</p>
  </div>
  <div class="grid cols-3">
    <div class="card">
      <h3>For operators</h3>
      <p>Replace copy-paste workflows and manual triage with one environment for search, review, and CRM-ready output.</p>
    </div>
    <div class="card">
      <h3>For agencies</h3>
      <p>Run prospecting and enrichment across clients without rebuilding the stack every time a workflow changes.</p>
    </div>
    <div class="card">
      <h3>For AI teams</h3>
      <p>Give your copilots and internal agents a live lead operations layer they can call through MCP instead of bolting onto consumer chat products.</p>
    </div>
  </div>
</section>

<section class="panel stack">
  <div class="quote">
    <p><strong>LeadsMCP is for teams that want their lead generation stack to behave like an operating system, not a pile of exports.</strong></p>
    <p>If your team needs live search, structured review, AI connectivity, and direct CRM handoff in one place, this is the layer that ties those pieces together.</p>
  </div>
</section>

<section class="panel stack">
  <div class="section-head">
    <span class="kicker">Best Use Cases</span>
    <h2>Where LeadsMCP creates the most leverage</h2>
    <p>Teams usually get the most value when they use LeadsMCP as an operating layer across search, enrichment, and routing, not as a standalone list download tool.</p>
  </div>
  <div class="grid cols-2">
    <div class="card">
      <h3>Outbound and prospecting</h3>
      <ul class="checklist">
        <li>Find businesses in specific markets and territories</li>
        <li>Enrich websites for contact opportunities</li>
        <li>Review structured records before a rep or workflow touches them</li>
      </ul>
    </div>
    <div class="card">
      <h3>MCP and AI workflow integration</h3>
      <ul class="checklist">
        <li>Connect AI workspaces to a live lead operations backend</li>
        <li>Use one endpoint for research, comparison, and CRM handoff</li>
        <li>Keep the human and automation path aligned around the same data model</li>
      </ul>
    </div>
  </div>
</section>

<section class="panel stack">
  <div class="section-head">
    <span class="kicker">Ready to Start</span>
    <h2>Run a first search, review the output, and see the system in motion</h2>
    <p>The fastest way to understand LeadsMCP is to use it. Start with a live preview, inspect the structured results, and connect the workflow into your CRM or MCP client once the data quality looks right.</p>
  </div>
  <div class="nav-links">
    <a class="btn primary" href="{cta}">Start Your Free Preview</a>
    <a class="btn" href="{github_url}">View API and MCP Docs</a>
    <a class="btn" href="{base_url}/support/">Talk to Support</a>
  </div>
</section>

<div class="footer">Canonical URL: <code>{canonical_url}</code></div>
</div>"""
    return _html_shell(title='LeadsMCP | MCP Lead Generation Software', body=body)


def build_support_page(*, base_url: str, install_url: str, github_url: str) -> str:
    body = f"""<div class="wrap stack">{_page_nav(base_url, github_url)}<section class="panel stack"><span class="kicker">Support</span><h1>LeadsMCP support and deployment help</h1><p>Use this page for install questions, deployment guidance, MCP connection help, GoHighLevel auth issues, and billing-related export behavior.</p><div class="grid cols-3"><div class="card"><h3>Best first checks</h3><ul><li>Confirm <code>x-mcp-secret</code> is set</li><li>Confirm GHL token and location ID are valid</li><li>Confirm OAuth redirect URLs match exactly</li></ul></div><div class="card"><h3>Useful endpoints</h3><ul><li><code>/health</code></li><li><code>/mcp</code></li><li><code>/oauth/ghl/start</code></li><li><code>/oauth/ghl/callback</code></li></ul></div><div class="card"><h3>Escalation paths</h3><ul><li>Deployment issues</li><li>GHL install issues</li><li>Token refresh issues</li><li>CRM write verification</li></ul></div></div><div class="nav-links"><a class="btn primary" href="{install_url or (base_url + '/oauth/ghl/start')}">Open Install Flow</a><a class="btn" href="{base_url}/contact/">Contact</a></div></section></div>"""
    return _html_shell(title='LeadsMCP Support', body=body)


def build_contact_page(*, base_url: str, github_url: str, install_url: str) -> str:
    body = f"""<div class="wrap stack">{_page_nav(base_url, github_url)}<section class="panel stack"><span class="kicker">Contact</span><h1>Talk to us about LeadsMCP</h1><p>Use LeadsMCP as a private commercial server for live lead search, MCP-connected workflows, and GoHighLevel handoff. Reach out for demos, licensing, managed setup, or enterprise deployment help.</p><div class="grid cols-3"><div class="card"><h3>Commercial</h3><p>Private repo access, managed setup, and customer onboarding.</p></div><div class="card"><h3>Technical</h3><p>MCP integration, CRM sync, token refresh, and deployment support.</p></div><div class="card"><h3>Next step</h3><p>Start the install flow or use the GitHub repo to review the product surface.</p></div></div><div class="nav-links"><a class="btn primary" href="{install_url or (base_url + '/oauth/ghl/start')}">Install LeadsMCP</a><a class="btn" href="{github_url}">GitHub</a></div></section></div>"""
    return _html_shell(title='Contact LeadsMCP', body=body)


def build_install_success_page(*, base_url: str, github_url: str, install_url: str, webhook_url: str) -> str:
    body = f"""<div class="wrap stack">{_page_nav(base_url, github_url)}<section class="panel stack"><span class="kicker">Installed</span><h1>LeadsMCP is installed successfully</h1><p>Your GoHighLevel app install completed. This page confirms the connection and can relay the install code to your automation webhook when present.</p><div class="card"><p><strong>Next:</strong> connect an MCP client, verify the subaccount context, and run a first search plus CRM write test.</p></div><div class="nav-links"><a class="btn primary" href="{install_url or (base_url + '/oauth/ghl/start')}">Install Again</a><a class="btn" href="{base_url}/support/">Support</a></div></section><script>const p=new URLSearchParams(window.location.search);const code=p.get('code');const webhook={json.dumps(webhook_url)};if(code&&webhook){{fetch(webhook,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{code}})}}).catch(()=>{{}});}}</script></div>"""
    return _html_shell(title='LeadsMCP Installed', body=body)


class MCPSecretMiddleware(BaseHTTPMiddleware):
    """Gate non-public routes.

    Authentication precedence for protected routes:
      1) A valid connector OAuth Bearer access token (when connector OAuth is on).
      2) The legacy ``x-mcp-secret`` header matching ``MCP_SECRET``.
    When neither is present the request is rejected. For the ``/mcp`` resource a
    ``WWW-Authenticate`` challenge pointing at the protected-resource metadata is
    returned so MCP clients can bootstrap discovery + Dynamic Client Registration.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Retired paths fall through to routing (-> 404) instead of the 401 gate.
        if path in RETIRED_PATHS:
            return await call_next(request)

        if _is_public_path(path):
            return await call_next(request)

        required_secret = os.getenv("MCP_SECRET", "").strip()
        oauth_on = connector_oauth.connector_oauth_enabled()

        # No auth configured at all -> preserve historical open behavior.
        if not required_secret and not oauth_on:
            return await call_next(request)

        # 1) Connector OAuth Bearer access token.
        if oauth_on:
            auth_header = request.headers.get("authorization", "").strip()
            if auth_header.lower().startswith("bearer "):
                bearer = auth_header[7:].strip()
                token_record = await connector_oauth.validate_bearer(bearer)
                if token_record:
                    token_data = token_record.get("data") or {}
                    if isinstance(token_data, str):
                        try:
                            token_data = json.loads(token_data)
                        except (json.JSONDecodeError, ValueError):
                            token_data = {}
                    binding = token_data.get("installation") or {}
                    install_key = str(binding.get("install_key") or "").strip()
                    if LEADSMCP_MODE != DEVELOPER_MODE and not install_key:
                        return JSONResponse(
                            {
                                "error": "installation_required",
                                "message": "Connector token is not bound to a CRM installation.",
                            },
                            status_code=403,
                        )
                    if install_key:
                        installation = await get_installation(install_key=install_key)
                        if not installation:
                            return JSONResponse(
                                {
                                    "error": "installation_unavailable",
                                    "message": "The bound CRM installation is unavailable.",
                                },
                                status_code=403,
                            )
                        if installation.get("payment_status") == "FAILED":
                            return JSONResponse(
                                {
                                    "error": "subscription_inactive",
                                    "message": "Marketplace subscription payment is inactive.",
                                },
                                status_code=402,
                            )
                        ghl_access_token = _decrypt_from_store(
                            str(installation.get("access_token_encrypted") or "")
                        )
                        location_id = str(
                            installation.get("location_id") or ""
                        ).strip()
                        if not ghl_access_token or not location_id:
                            return JSONResponse(
                                {
                                    "error": "location_authorization_required",
                                    "message": "A location-level CRM authorization is required.",
                                },
                                status_code=403,
                            )
                        request.scope["headers"] = [
                            *request.scope.get("headers", []),
                            (b"x-ghl-token", ghl_access_token.encode("utf-8")),
                            (
                                b"x-ghl-location-id",
                                location_id.encode("utf-8"),
                            ),
                        ]
                        request.state.ghl_installation = installation
                    return await call_next(request)

        # 2) Legacy x-mcp-secret compatibility.
        if required_secret:
            provided_secret = request.headers.get("x-mcp-secret", "").strip()
            if provided_secret and hmac.compare_digest(provided_secret, required_secret):
                return await call_next(request)

        return self._unauthorized(request, oauth_on)

    @staticmethod
    def _unauthorized(request: Request, oauth_on: bool) -> JSONResponse:
        headers: dict[str, str] = {}
        is_mcp = request.url.path == "/mcp" or request.url.path.startswith("/mcp/")
        if oauth_on and is_mcp:
            base = _public_base_url(request)
            headers["WWW-Authenticate"] = connector_oauth.www_authenticate_challenge(
                base, error="invalid_token", description="Missing or invalid access token."
            )
        return JSONResponse(
            {
                "error": "Unauthorized",
                "message": "Provide a valid OAuth Bearer token or x-mcp-secret header.",
            },
            status_code=401,
            headers=headers,
        )


def build_ghl_tenant_headers(
    incoming_headers: dict[str, str],
) -> dict[str, str]:
    """Normalize tenant-specific GHL headers with explicit precedence."""
    tenant_headers: dict[str, str] = {}
    ghl_token = incoming_headers.get("x-ghl-token") or incoming_headers.get(
        "authorization"
    )
    if ghl_token:
        normalized_token = ghl_token.strip()
        if (
            normalized_token
            and not normalized_token.lower().startswith("bearer ")
        ):
            normalized_token = f"Bearer {normalized_token}"
        if normalized_token:
            tenant_headers["authorization"] = normalized_token

    ghl_location = incoming_headers.get(
        "x-ghl-location-id"
    ) or incoming_headers.get("locationid")
    if ghl_location:
        tenant_headers["locationid"] = ghl_location.strip()

    ghl_version = incoming_headers.get(
        "x-ghl-version"
    ) or incoming_headers.get("version")
    if ghl_version:
        tenant_headers["version"] = ghl_version.strip()
    return tenant_headers


GHL_TENANT_HEADER_NAMES = {
    "authorization",
    "locationid",
    "version",
    "x-ghl-token",
    "x-ghl-location-id",
    "x-ghl-version",
}


class GHLTenantAwareTransport(StreamableHttpTransport):
    """
    Streamable HTTP transport that forwards tenant-specific GHL headers per request.
    Header priority:
      1) x-ghl-token / x-ghl-location-id / x-ghl-version
      2) authorization / locationid / version
      3) static defaults from env (self.headers)
    """

    @contextlib.asynccontextmanager
    async def connect_session(self, **session_kwargs) -> AsyncIterator[ClientSession]:
        incoming_headers = get_http_headers(
            include={
                "authorization",
                "locationid",
                "version",
                "x-ghl-token",
                "x-ghl-location-id",
                "x-ghl-version",
            }
        )

        tenant_headers = build_ghl_tenant_headers(incoming_headers)
        headers = self.headers | tenant_headers

        timeout: httpx.Timeout | None = None
        if session_kwargs.get("read_timeout_seconds") is not None:
            read_timeout_seconds = cast(
                datetime.timedelta, session_kwargs.get("read_timeout_seconds")
            )
            timeout = httpx.Timeout(30.0, read=read_timeout_seconds.total_seconds())

        if self.httpx_client_factory is not None:
            http_client = self.httpx_client_factory(
                headers=headers,
                auth=self.auth,
                follow_redirects=True,  # type: ignore[call-arg]
                **({"timeout": timeout} if timeout else {}),
            )
        else:
            http_client = create_mcp_http_client(
                headers=headers,
                timeout=timeout,
                auth=self.auth,
            )

        async with (
            http_client,
            streamable_http_client(self.url, http_client=http_client) as transport,
        ):
            read_stream, write_stream, get_session_id = transport
            self._get_session_id_cb = get_session_id
            async with ClientSession(
                read_stream, write_stream, **session_kwargs
            ) as session:
                yield session


def _required_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_production_env() -> bool:
    for key in ("ENV", "APP_ENV", "PYTHON_ENV", "NODE_ENV", "VERCEL_ENV"):
        if _truthy(os.getenv(key, "")):
            return True
        if os.getenv(key, "").strip().lower() in {"production", "prod"}:
            return True
    return False


def _cors_allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    if _is_production_env():
        return []
    return ["*"]


def _state_secret() -> str:
    candidate = os.getenv("GHL_OAUTH_STATE_SECRET", "").strip() or os.getenv("MCP_SECRET", "").strip()
    if not candidate:
        raise ValueError("Set GHL_OAUTH_STATE_SECRET or MCP_SECRET to sign OAuth state.")
    return candidate


def _state_ttl_seconds() -> int:
    raw = os.getenv("GHL_OAUTH_STATE_TTL_SECONDS", "900").strip()
    try:
        ttl = int(raw)
    except ValueError:
        ttl = 900
    return max(ttl, 60)


def _install_store_path() -> Path:
    raw = os.getenv("GHL_INSTALL_STORE_PATH", "/tmp/leadsmcp_ghl_installs.jsonl").strip()
    return Path(raw)


def _install_encryption_secret() -> str:
    return (
        os.getenv("GHL_INSTALL_ENCRYPTION_SECRET", "").strip()
        or os.getenv("GHL_OAUTH_STATE_SECRET", "").strip()
        or os.getenv("MCP_SECRET", "").strip()
    )


def _install_store_cipher() -> Fernet:
    secret = _install_encryption_secret()
    if not secret:
        raise ValueError(
            "Missing install encryption secret. Set GHL_INSTALL_ENCRYPTION_SECRET "
            "(or GHL_OAUTH_STATE_SECRET / MCP_SECRET fallback)."
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt_for_store(value: str) -> str:
    if not value:
        return ""
    return _install_store_cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt_from_store(value: str) -> str:
    if not value:
        return ""
    return _install_store_cipher().decrypt(value.encode("utf-8")).decode("utf-8")


def _load_install_records() -> list[dict[str, Any]]:
    path = _install_store_path()
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
    except Exception:
        return []
    return records


def _latest_install_record(*, location_id: str = "", company_id: str = "") -> dict[str, Any] | None:
    wanted_location = str(location_id or "").strip()
    wanted_company = str(company_id or "").strip()
    if not wanted_location and not wanted_company:
        return None

    records = _load_install_records()
    for record in reversed(records):
        if not isinstance(record, dict):
            continue
        if wanted_location and str(record.get("location_id") or "").strip() == wanted_location:
            return record
        if wanted_company and str(record.get("company_id") or "").strip() == wanted_company:
            return record
    return None


async def _persist_ghl_install_record(
    *,
    token_payload: dict[str, Any],
    redirect_uri: str,
    user_type: str,
    state_payload: dict[str, Any] | None,
    source: str,
) -> dict[str, Any]:
    location_id = (
        token_payload.get("locationId")
        or token_payload.get("location_id")
        or token_payload.get("location")
        or ""
    )
    company_id = token_payload.get("companyId") or token_payload.get("company_id") or ""
    user_id = token_payload.get("userId") or token_payload.get("user_id") or ""
    access_token = str(token_payload.get("access_token") or "").strip()
    refresh_token = str(token_payload.get("refresh_token") or "").strip()

    encrypted_access = _encrypt_for_store(access_token) if access_token else ""
    encrypted_refresh = _encrypt_for_store(refresh_token) if refresh_token else ""
    access_fingerprint = hashlib.sha256(access_token.encode("utf-8")).hexdigest() if access_token else ""
    install_key = f"{company_id}:{location_id}" if company_id or location_id else ""
    if not install_key or not access_token:
        raise ValueError(
            "OAuth token response is missing the installation identity or access token."
        )

    state_tenant_id = ""
    state_customer_id = ""
    state_return_to = ""
    if isinstance(state_payload, dict):
        state_tenant_id = str(state_payload.get("tenant_id") or "").strip()
        state_customer_id = str(state_payload.get("customer_id") or "").strip()
        state_return_to = str(state_payload.get("return_to") or "").strip()

    record = {
        "saved_at": int(time.time()),
        "source": source,
        "install_key": install_key or None,
        "tenant_id": state_tenant_id or None,
        "customer_id": state_customer_id or None,
        "return_to": state_return_to or None,
        "company_id": str(company_id or ""),
        "location_id": str(location_id or ""),
        "user_id": str(user_id or ""),
        "user_type": user_type,
        "redirect_uri": redirect_uri,
        "scope": token_payload.get("scope"),
        "token_type": token_payload.get("token_type"),
        "access_token_expires_in": token_payload.get("expires_in"),
        "access_token_fingerprint_sha256": access_fingerprint,
        "access_token_encrypted": encrypted_access,
        "refresh_token_encrypted": encrypted_refresh,
        "installed": True,
        "uninstalled_at": None,
        "app_id": str(
            token_payload.get("appId")
            or token_payload.get("app_id")
            or os.getenv("GHL_APP_ID", "")
        ),
        "plan_id": str(
            token_payload.get("planId")
            or token_payload.get("plan_id")
            or ""
        ),
        "is_bulk_installation": bool(
            token_payload.get("isBulkInstallation", False)
        ),
        "install_to_future_locations": bool(
            token_payload.get("installToFutureLocations", False)
        ),
        "approve_all_locations": bool(
            token_payload.get("approveAllLocations", False)
        ),
        "approved_locations": token_payload.get("approvedLocations") or [],
        "payment_status": str(
            token_payload.get("paymentStatus") or "COMPLETE"
        ),
        "trial": token_payload.get("trial"),
    }

    store_result = await persist_install_record(record)

    return {
        "stored": True,
        **store_result,
        "install_key": install_key or None,
        "location_id": str(location_id or ""),
        "company_id": str(company_id or ""),
    }


async def _provision_bulk_locations(
    *,
    token_payload: dict[str, Any],
    redirect_uri: str,
) -> dict[str, Any]:
    user_type = str(
        token_payload.get("userType")
        or token_payload.get("user_type")
        or ""
    ).lower()
    is_bulk = bool(token_payload.get("isBulkInstallation"))
    if user_type != "company" and not is_bulk:
        return {"attempted": False, "provisioned": 0, "errors": []}

    company_id = str(
        token_payload.get("companyId")
        or token_payload.get("company_id")
        or ""
    ).strip()
    app_id = str(
        token_payload.get("appId")
        or token_payload.get("app_id")
        or os.getenv("GHL_APP_ID", "")
    ).strip()
    agency_access_token = str(
        token_payload.get("access_token") or ""
    ).strip()
    if not company_id or not app_id or not agency_access_token:
        return {
            "attempted": True,
            "provisioned": 0,
            "errors": ["Company token response is missing companyId, appId, or access_token."],
        }

    locations = await get_installed_locations(
        agency_access_token=agency_access_token,
        company_id=company_id,
        app_id=app_id,
    )
    location_ids = [
        str(item.get("_id") or item.get("locationId") or "").strip()
        for item in locations
        if item.get("isInstalled", True)
    ]
    location_ids = [location_id for location_id in location_ids if location_id]

    semaphore = asyncio.Semaphore(5)

    async def provision(location_id: str) -> tuple[str, str]:
        async with semaphore:
            try:
                location_token = await exchange_location_token(
                    agency_access_token=agency_access_token,
                    company_id=company_id,
                    location_id=location_id,
                )
                await _persist_ghl_install_record(
                    token_payload=location_token,
                    redirect_uri=redirect_uri,
                    user_type="Location",
                    state_payload=None,
                    source="bulk_location_exchange",
                )
                return location_id, ""
            except Exception as exc:
                return location_id, str(exc)

    results = await asyncio.gather(
        *(provision(location_id) for location_id in location_ids)
    )
    errors = [
        {"location_id": location_id, "error": error}
        for location_id, error in results
        if error
    ]
    return {
        "attempted": True,
        "discovered": len(location_ids),
        "provisioned": len(location_ids) - len(errors),
        "errors": errors,
    }


def _allow_callback_token_response() -> bool:
    # Token payload disclosure is disabled in every environment unless a
    # developer explicitly opts in. Preview deployments often contain real
    # credentials and must not be treated as safe places to echo tokens.
    value = os.getenv(
        "GHL_OAUTH_ALLOW_TOKEN_RESPONSE",
        os.getenv("GHL_OAUTH_ALLOW_TOKEN_RESPONSE_IN_PRODUCTION", "false"),
    )
    return _truthy(value)


def _append_query_params(url: str, params: dict[str, str]) -> str:
    parsed = urlparse(url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_items.update(params)
    return urlunparse(parsed._replace(query=urlencode(query_items)))


def _public_base_url(request: Request) -> str:
    configured = os.getenv("PUBLIC_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _coerce_int(value: Any, fallback: int | None = 0) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return fallback












































































def _sign_oauth_state(payload: dict[str, Any]) -> str:
    secret = _state_secret().encode("utf-8")
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return f"{body.hex()}.{signature}"


def _verify_oauth_state(state: str) -> dict[str, Any]:
    if "." not in state:
        raise ValueError("Malformed state.")
    body_hex, supplied_sig = state.split(".", 1)
    try:
        body = bytes.fromhex(body_hex)
    except ValueError as exc:
        raise ValueError("Malformed state payload.") from exc

    expected_sig = hmac.new(_state_secret().encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, supplied_sig):
        raise ValueError("State signature mismatch.")

    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("State payload must be an object.")

    issued_at = payload.get("iat")
    if not isinstance(issued_at, int):
        raise ValueError("State is missing iat.")
    if int(time.time()) - issued_at > _state_ttl_seconds():
        raise ValueError("State has expired.")
    return payload


def _installation_cookie_name() -> str:
    return os.getenv(
        "LEADSMCP_INSTALLATION_COOKIE",
        "leadsmcp_installation",
    ).strip() or "leadsmcp_installation"


def _sign_installation_cookie(install_key: str) -> str:
    payload = {
        "install_key": install_key,
        "exp": int(time.time()) + 30 * 24 * 60 * 60,
    }
    body = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    signature = hmac.new(
        _state_secret().encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def _verify_installation_cookie(value: str) -> dict[str, Any]:
    encoded, separator, supplied = value.partition(".")
    if not separator:
        raise ValueError("Malformed installation cookie.")
    expected = hmac.new(
        _state_secret().encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("Installation cookie signature mismatch.")
    padded = encoded + "=" * (-len(encoded) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    if int(payload.get("exp") or 0) < int(time.time()):
        raise ValueError("Installation cookie expired.")
    if not payload.get("install_key"):
        raise ValueError("Installation cookie is missing install_key.")
    return payload


def _attach_installation_cookie(
    response: Response,
    install_key: str,
) -> Response:
    if install_key:
        response.set_cookie(
            _installation_cookie_name(),
            _sign_installation_cookie(install_key),
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
    return response



def _oauth_redirect_uri(request: Request) -> str:
    configured = os.getenv("GHL_OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return str(request.url.replace(query=""))


def _oauth_user_type(fallback: str = "") -> str:
    return fallback.strip() or os.getenv("GHL_OAUTH_USER_TYPE", "").strip()


def _ghl_token_endpoint() -> str:
    return os.getenv("GHL_OAUTH_TOKEN_URL", "https://services.leadconnectorhq.com/oauth/token").strip()


async def _exchange_ghl_authorization_code(
    *,
    code: str,
    redirect_uri: str,
    user_type: str,
) -> dict[str, Any]:
    form = {
        "client_id": _required_env("GHL_CLIENT_ID"),
        "client_secret": _required_env("GHL_CLIENT_SECRET"),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if user_type:
        form["user_type"] = user_type
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _ghl_token_endpoint(),
            data=form,
            headers={"Accept": "application/json"},
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if response.is_error:
        raise RuntimeError(f"GHL OAuth token exchange failed ({response.status_code}): {payload}")
    if not isinstance(payload, dict):
        raise RuntimeError("GHL token response is not a JSON object.")
    return payload


async def _refresh_ghl_access_token(
    *,
    refresh_token: str,
    redirect_uri: str,
    user_type: str,
) -> dict[str, Any]:
    form = {
        "client_id": _required_env("GHL_CLIENT_ID"),
        "client_secret": _required_env("GHL_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "redirect_uri": redirect_uri,
    }
    if user_type:
        form["user_type"] = user_type
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _ghl_token_endpoint(),
            data=form,
            headers={"Accept": "application/json"},
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if response.is_error:
        raise RuntimeError(f"GHL token refresh failed ({response.status_code}): {payload}")
    if not isinstance(payload, dict):
        raise RuntimeError("GHL refresh response is not a JSON object.")
    return payload


def _oauth_result_payload(
    token_payload: dict[str, Any],
    *,
    redirect_uri: str,
    user_type: str,
    state_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    access_token = token_payload.get("access_token")
    connection_headers = {
        "x-ghl-token": access_token,
        "x-ghl-location-id": (
            token_payload.get("locationId")
            or token_payload.get("location_id")
            or token_payload.get("location")
            or ""
        ),
        "x-ghl-version": os.getenv("GHL_API_VERSION", "2021-07-28"),
    }
    return {
        "ok": True,
        "grant_type": token_payload.get("grant_type"),
        "user_type": user_type,
        "redirect_uri": redirect_uri,
        "access_token": access_token,
        "refresh_token": token_payload.get("refresh_token"),
        "token_type": token_payload.get("token_type"),
        "expires_in": token_payload.get("expires_in"),
        "scope": token_payload.get("scope"),
        "company_id": token_payload.get("companyId") or token_payload.get("company_id"),
        "location_id": connection_headers["x-ghl-location-id"],
        "user_id": token_payload.get("userId") or token_payload.get("user_id"),
        "connection_headers": connection_headers,
        "state_payload": state_payload,
        "raw": token_payload,
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────
orchestrator = FastMCP(
    name="AI Orchestrator",
    instructions="""
You are an AI lead-generation and CRM agent with access to three service groups:

OUTSCRAPER tools (namespace: outscraper_):
  - outscraper_google_maps_search     → Find businesses on Google Maps by location/category
  - outscraper_google_maps_reviews    → Fetch reviews for a business
  - outscraper_emails_and_contacts    → Scrape domains for emails, phones, and contact channels
  - outscraper_email_validator        → Check email deliverability before importing
  - outscraper_phones_enricher        → Validate phones and get carrier data
  - outscraper_similarweb             → Pull website analytics and traffic signals
  - outscraper_google_search          → Research a prospect before outreach
  - outscraper_get_request_results    → Poll a pending async Outscraper request

GHL v2 tools (namespace: ghl_):
  - ghl_search             → Search CRM records across the connected location
  - ghl_fetch              → Fetch complete records by ID
  - ghl_search_operations  → Discover any permitted HighLevel API operation by intent
  - ghl_describe_operation → Retrieve the required schema for an operation
  - ghl_execute_operation  → Execute a discovered operation using the described schema
  - The v2 operation catalog covers all domains granted by the connected OAuth/PIT scopes.
  - GHL tools use per-request tenant credentials and remain restricted to one location.

Stripe tools (namespace: stripe_):
  - stripe_ensure_customer_profile               → Create/update customer before showing full lead details
  - stripe_analyze_qualified_lead_export         → Compute qualified leads + per-company breakdown + estimate
  - stripe_plan_qualified_lead_export_billing    → Decide checkout/permission/ready state for export batch
  - stripe_get_customer_export_access            → Check subscription/paywall status
  - stripe_create_usage_checkout_session         → Start metered subscription checkout
  - stripe_record_qualified_lead_export          → Log billable lead export usage event with batch guards

STANDARD WORKFLOW:
  1. Collect user profile details first: full name, first name, last name, email, phone
  2. Call stripe_ensure_customer_profile and retain stripe_customer_id for the session
  3. Call outscraper_google_maps_search or outscraper_emails_and_contacts → raw lead list
  4. Call outscraper_email_validator / outscraper_phones_enricher → confirm quality
  5. Keep search/preview free: show results and company lead counts without billing
  6. Before any CRM export:
     a) Call stripe_analyze_qualified_lead_export on company payloads
     b) Generate/retain export_batch_id and tenant_id
     c) Call stripe_plan_qualified_lead_export_billing with qualified_leads + export_batch_id
     d) If checkout_required, present checkout URL and wait for completion
     e) If permission_required, ask explicit user consent for this exact batch cost
  7. After approval, call stripe_record_qualified_lead_export
     - include export_batch_id, tenant_id, consent_granted=true
     - include tier_a_leads/tier_b_leads if available (or leads_exported fallback)
  8. Only then perform GHL writes (contacts/opportunities/tags)

GHL tenancy:
  - Prefer tenant headers from the request:
    x-ghl-token, x-ghl-location-id, x-ghl-version(optional)
  - Fallback to server defaults if tenant headers are absent.

Field mapping: name->firstName+lastName, phone->phone, site->website,
full_address->address1, city->city, state->state, postal_code->postalCode
Always tag contacts with 'outscraper' plus the search category/city.
Never export to GHL without recording stripe usage for that export batch ID.

TempMail tools (namespace: tempmail_):
  - tempmail_list_domains               → Available disposable domains for the account tier
  - tempmail_create_mailbox             → Create one temporary inbox
  - tempmail_create_campaign_mailboxes  → Bulk-create numbered inboxes for a campaign
  - tempmail_list_mailboxes             → List existing inboxes and their IDs
  - tempmail_delete_mailbox             → Tear down an inbox
  - tempmail_list_mails                 → List messages in an inbox
  - tempmail_read_mail                  → Read one message in full
  - tempmail_delete_mail                → Delete one message
  - tempmail_wait_for_mail              → Poll an inbox until a matching message arrives
  - tempmail_extract_verification_code  → Pull OTP codes / confirmation links from a message

TempMail usage:
  - Always call tempmail_list_domains before tempmail_create_mailbox; 'domain' must
    be one of the returned values.
  - lifespan must be 0, 300, 600, 900, 1200, or 1800 seconds (0 = no auto-expiry).
  - Requires TWO credentials: the RapidAPI key and a separate TempMail.so account
    bearer token. Per-tenant callers send 'x-tempmail-rapidapi-key' and
    'x-tempmail-token' headers; otherwise server env defaults are used.
  - Use disposable inboxes for tool signups, deliverability seed tests, and burner
    reply addresses only. Never present a temp inbox as a prospect's real contact
    address, and never write one into a GHL contact record.
""",
)

# ── Mount local Outscraper sub-server ──────────────────────────────────────────
orchestrator.mount(outscraper_mcp, namespace="outscraper")
orchestrator.mount(stripe_mcp, namespace="stripe")
orchestrator.mount(tempmail_mcp, namespace="tempmail")

# ── Proxy the GHL native MCP (remote HTTP) ────────────────────────────────────
DEFAULT_GHL_TOKEN = os.getenv("GHL_PIT_TOKEN", "").strip()
DEFAULT_GHL_LOCATION = os.getenv("GHL_LOCATION_ID", "").strip()
DEFAULT_GHL_VERSION = os.getenv("GHL_API_VERSION", "2021-07-28").strip()

default_ghl_headers: dict[str, str] = {}
if DEFAULT_GHL_TOKEN:
    bearer = DEFAULT_GHL_TOKEN if DEFAULT_GHL_TOKEN.lower().startswith("bearer ") else f"Bearer {DEFAULT_GHL_TOKEN}"
    default_ghl_headers["authorization"] = bearer
if DEFAULT_GHL_LOCATION:
    default_ghl_headers["locationid"] = DEFAULT_GHL_LOCATION
if DEFAULT_GHL_VERSION:
    default_ghl_headers["version"] = DEFAULT_GHL_VERSION

ghl_transport = GHLTenantAwareTransport(
    url=os.getenv("GHL_MCP_URL", "https://services.leadconnectorhq.com/mcp/anthropic/v2").strip(),
    headers=default_ghl_headers,
)
ghl_backend = Client(ghl_transport)


ghl_proxy = create_proxy(ghl_backend, name="GHL Proxy")
orchestrator.mount(ghl_proxy, namespace="ghl")

# The public endpoint fails closed to the approved nine-tool Marketplace contract.
# A controlled developer deployment can opt into the underlying catalog explicitly.
LEADSMCP_MODE = load_marketplace_mode()
orchestrator.add_middleware(MarketplaceToolCatalogMiddleware(mode=LEADSMCP_MODE))

# Retain the legacy GHL group allowlist only for developer-mode compatibility.
if (
    LEADSMCP_MODE == DEVELOPER_MODE
    and os.getenv("GHL_V2_TOOL_ALLOWLIST_ENABLED", "false").strip().lower()
    in {"1", "true", "yes", "on"}
):
    orchestrator.add_middleware(GHLToolAllowlistMiddleware())


# ── Deterministic GHL contact writes ─────────────────────────────────────────
GHL_REST_BASE_URL = os.getenv(
    "GHL_API_BASE_URL",
    "https://services.leadconnectorhq.com",
).strip().rstrip("/")


def _resolve_ghl_rest_credentials() -> tuple[str, str, str]:
    incoming = get_http_headers(include=set(GHL_TENANT_HEADER_NAMES))
    tenant = build_ghl_tenant_headers(incoming)
    authorization = (
        tenant.get("authorization")
        or default_ghl_headers.get("authorization", "")
    ).strip()
    location_id = (
        tenant.get("locationid") or DEFAULT_GHL_LOCATION
    ).strip()
    version = (
        tenant.get("version")
        or DEFAULT_GHL_VERSION
        or "2021-07-28"
    ).strip()
    return authorization, location_id, version


async def _post_create_contact(
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
    http_client: httpx.AsyncClient | None = None,
) -> tuple[int, Any]:
    async def send(client: httpx.AsyncClient) -> tuple[int, Any]:
        response = await client.post(url, json=body, headers=headers)
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"raw": response.text}
        return response.status_code, payload

    if http_client is not None:
        return await send(http_client)
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await send(client)


async def _deterministic_contact_write(
    *,
    endpoint: str,
    fields: dict[str, Any],
    tags: list[str] | str | None,
    custom_fields: list[dict[str, Any]] | dict[str, Any] | None,
    additional_fields: dict[str, Any] | None,
    location_id: str | None,
) -> dict[str, Any]:
    authorization, resolved_location, version = (
        _resolve_ghl_rest_credentials()
    )
    if not authorization:
        raise ToolError(
            json.dumps(
                ContactCreateError(
                    "auth_error",
                    "No CRM authorization token is available.",
                ).to_dict()
            )
        )
    try:
        body = build_create_contact_body(
            location_id=location_id or resolved_location,
            fields=fields,
            tags=tags,
            custom_fields=custom_fields,
            additional_fields=additional_fields,
        )
    except ContactCreateError as exc:
        raise ToolError(json.dumps(exc.to_dict())) from exc

    try:
        status_code, payload = await _post_create_contact(
            f"{GHL_REST_BASE_URL}{endpoint}",
            headers={
                "Authorization": authorization,
                "Version": version,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            body=body,
        )
    except httpx.HTTPError as exc:
        raise ToolError(
            json.dumps(
                ContactCreateError(
                    "transport_error",
                    f"CRM API request failed: {type(exc).__name__}.",
                ).to_dict()
            )
        ) from exc
    try:
        result = map_create_contact_response(status_code, payload)
    except ContactCreateError as exc:
        raise ToolError(json.dumps(exc.to_dict())) from exc
    if endpoint.endswith("/upsert") and isinstance(payload, dict):
        if payload.get("new") is False:
            result["status"] = "updated"
    return result


@orchestrator.tool(
    name="ghl_contacts_create_contact",
    description=(
        "Deterministically create a CRM contact through POST /contacts/. "
        "This performs a real write; confirm user intent before calling."
    ),
)
async def ghl_contacts_create_contact(
    firstName: str | None = None,
    lastName: str | None = None,
    name: str | None = None,
    companyName: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address1: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postalCode: str | None = None,
    country: str | None = None,
    website: str | None = None,
    timezone: str | None = None,
    tags: list[str] | str | None = None,
    source: str | None = None,
    customFields: list[dict[str, Any]] | dict[str, Any] | None = None,
    additionalFields: dict[str, Any] | None = None,
    locationId: str | None = None,
) -> dict[str, Any]:
    return await _deterministic_contact_write(
        endpoint="/contacts/",
        fields={
            "firstName": firstName,
            "lastName": lastName,
            "name": name,
            "companyName": companyName,
            "email": email,
            "phone": phone,
            "address1": address1,
            "city": city,
            "state": state,
            "postalCode": postalCode,
            "country": country,
            "website": website,
            "timezone": timezone,
            "source": source,
        },
        tags=tags,
        custom_fields=customFields,
        additional_fields=additionalFields,
        location_id=locationId,
    )


@orchestrator.tool(
    name="ghl_contacts_upsert_contact",
    description=(
        "Deterministically create or update a CRM contact through "
        "POST /contacts/upsert. This performs a real write."
    ),
)
async def ghl_contacts_upsert_contact(
    firstName: str | None = None,
    lastName: str | None = None,
    name: str | None = None,
    companyName: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address1: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postalCode: str | None = None,
    country: str | None = None,
    website: str | None = None,
    timezone: str | None = None,
    tags: list[str] | str | None = None,
    source: str | None = None,
    customFields: list[dict[str, Any]] | dict[str, Any] | None = None,
    additionalFields: dict[str, Any] | None = None,
    locationId: str | None = None,
) -> dict[str, Any]:
    return await _deterministic_contact_write(
        endpoint="/contacts/upsert",
        fields={
            "firstName": firstName,
            "lastName": lastName,
            "name": name,
            "companyName": companyName,
            "email": email,
            "phone": phone,
            "address1": address1,
            "city": city,
            "state": state,
            "postalCode": postalCode,
            "country": country,
            "website": website,
            "timezone": timezone,
            "source": source,
        },
        tags=tags,
        custom_fields=customFields,
        additional_fields=additionalFields,
        location_id=locationId,
    )

# ── OAuth routes (GoHighLevel Marketplace install flow) ──────────────────────
@orchestrator.custom_route("/oauth/ghl/start", methods=["GET"])
async def ghl_oauth_start(request: Request):
    install_url = os.getenv("GHL_OAUTH_INSTALL_URL", "").strip()
    if not install_url:
        return JSONResponse(
            {
                "error": "missing_install_url",
                "message": "Set GHL_OAUTH_INSTALL_URL to your marketplace install URL.",
            },
            status_code=500,
        )

    state_payload: dict[str, Any] = {
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
    }
    for key in ("tenant_id", "customer_id", "return_to", "user_type"):
        value = request.query_params.get(key, "").strip()
        if value:
            state_payload[key] = value

    signed_state = _sign_oauth_state(state_payload)
    redirect_to = _append_query_params(install_url, {"state": signed_state})
    return RedirectResponse(url=redirect_to, status_code=307)


@orchestrator.custom_route("/oauth/ghl/callback", methods=["GET"])
async def ghl_oauth_callback(request: Request):
    error = request.query_params.get("error", "").strip()
    if error:
        return JSONResponse(
            {
                "error": "oauth_error",
                "provider_error": error,
                "message": request.query_params.get("error_description", "").strip() or "OAuth callback returned an error.",
            },
            status_code=400,
        )

    code = request.query_params.get("code", "").strip()
    if not code:
        return JSONResponse(
            {"error": "missing_code", "message": "Missing 'code' query param in callback."},
            status_code=400,
        )

    state_value = request.query_params.get("state", "").strip()
    state_payload: dict[str, Any] | None = None
    require_state = _truthy(os.getenv("GHL_OAUTH_REQUIRE_STATE", "false"))
    if state_value:
        try:
            state_payload = _verify_oauth_state(state_value)
        except ValueError as exc:
            return JSONResponse(
                {"error": "invalid_state", "message": str(exc)},
                status_code=400,
            )
    elif require_state:
        return JSONResponse(
            {"error": "missing_state", "message": "State is required but was not provided."},
            status_code=400,
        )

    user_type = _oauth_user_type(
        request.query_params.get("user_type", "").strip()
        or (str(state_payload.get("user_type")) if state_payload and state_payload.get("user_type") else "")
    )
    redirect_uri = _oauth_redirect_uri(request)

    try:
        token_payload = await _exchange_ghl_authorization_code(
            code=code,
            redirect_uri=redirect_uri,
            user_type=user_type,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": "token_exchange_failed", "message": str(exc)},
            status_code=502,
        )
    user_type = str(
        token_payload.get("userType")
        or token_payload.get("user_type")
        or user_type
        or "Location"
    )

    result = _oauth_result_payload(
        token_payload,
        redirect_uri=redirect_uri,
        user_type=user_type,
        state_payload=state_payload,
    )

    store_status: dict[str, Any]
    try:
        store_status = await _persist_ghl_install_record(
            token_payload=token_payload,
            redirect_uri=redirect_uri,
            user_type=user_type,
            state_payload=state_payload,
            source="oauth_callback",
        )
    except Exception as exc:
        if LEADSMCP_MODE != DEVELOPER_MODE:
            return JSONResponse(
                {
                    "error": "install_storage_unavailable",
                    "message": str(exc),
                },
                status_code=503,
            )
        store_status = {"stored": False, "error": str(exc)}

    try:
        bulk_status = await _provision_bulk_locations(
            token_payload=token_payload,
            redirect_uri=redirect_uri,
        )
    except Exception as exc:
        bulk_status = {
            "attempted": True,
            "provisioned": 0,
            "errors": [str(exc)],
        }

    install_key = str(store_status.get("install_key") or "")
    success_redirect = os.getenv("GHL_OAUTH_SUCCESS_REDIRECT_URL", "").strip()
    if success_redirect:
        redirect_params = {
            "status": "connected",
            "company_id": str(result.get("company_id") or ""),
            "location_id": str(result.get("location_id") or ""),
            "user_type": str(user_type),
            "tokens_hidden": "true",
            "install_stored": "true" if store_status.get("stored") else "false",
            "locations_provisioned": str(
                bulk_status.get("provisioned") or 0
            ),
        }
        response = RedirectResponse(
            url=_append_query_params(success_redirect, redirect_params),
            status_code=303,
        )
        return _attach_installation_cookie(response, install_key)

    if not _allow_callback_token_response():
        response = JSONResponse(
            {
                "ok": True,
                "status": "connected",
                "redirect_uri": redirect_uri,
                "user_type": user_type,
                "company_id": str(result.get("company_id") or ""),
                "location_id": str(result.get("location_id") or ""),
                "tokens_hidden": True,
                "install_stored": bool(store_status.get("stored")),
                "bulk_provisioning": bulk_status,
            }
        )
        return _attach_installation_cookie(response, install_key)

    result["install_store"] = store_status
    result["bulk_provisioning"] = bulk_status
    return _attach_installation_cookie(JSONResponse(result), install_key)


@orchestrator.custom_route("/leadsmcp/install", methods=["GET"])
async def ghl_oauth_callback_alias(request: Request):
    """
    Alias callback route to support marketplace apps configured with:
      https://<domain>/leadsmcp/install
    """
    return await ghl_oauth_callback(request)


@orchestrator.custom_route("/leadsmcp-install", methods=["GET"])
@orchestrator.custom_route("/leadsmcp-install/", methods=["GET"])
async def ghl_oauth_callback_alias_hyphen(request: Request):
    """
    Alias callback route to support marketplace apps configured with:
      https://<domain>/leadsmcp-install/
    """
    return await ghl_oauth_callback(request)


@orchestrator.custom_route("/oauth/ghl/exchange", methods=["POST"])
async def ghl_oauth_exchange(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    code = str(body.get("code", "")).strip()
    if not code:
        return JSONResponse(
            {"error": "missing_code", "message": "Request JSON must include 'code'."},
            status_code=400,
        )

    user_type = _oauth_user_type(str(body.get("user_type", "")).strip())
    redirect_uri = str(body.get("redirect_uri", "")).strip() or _oauth_redirect_uri(request)
    try:
        token_payload = await _exchange_ghl_authorization_code(
            code=code,
            redirect_uri=redirect_uri,
            user_type=user_type,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": "token_exchange_failed", "message": str(exc)},
            status_code=502,
        )
    user_type = str(
        token_payload.get("userType")
        or token_payload.get("user_type")
        or user_type
        or "Location"
    )
    result = _oauth_result_payload(
        token_payload,
        redirect_uri=redirect_uri,
        user_type=user_type,
    )
    try:
        result["install_store"] = await _persist_ghl_install_record(
            token_payload=token_payload,
            redirect_uri=redirect_uri,
            user_type=user_type,
            state_payload=None,
            source="oauth_exchange",
        )
    except Exception as exc:
        if LEADSMCP_MODE != DEVELOPER_MODE:
            return JSONResponse(
                {"error": "install_storage_unavailable", "message": str(exc)},
                status_code=503,
            )
        result["install_store"] = {"stored": False, "error": str(exc)}
    return JSONResponse(result)


@orchestrator.custom_route("/oauth/ghl/refresh", methods=["POST"])
async def ghl_oauth_refresh(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    refresh_token = str(body.get("refresh_token", "")).strip()
    if not refresh_token:
        return JSONResponse(
            {"error": "missing_refresh_token", "message": "Request JSON must include 'refresh_token'."},
            status_code=400,
        )

    user_type = _oauth_user_type(str(body.get("user_type", "")).strip())
    redirect_uri = str(body.get("redirect_uri", "")).strip() or _oauth_redirect_uri(request)
    try:
        token_payload = await _refresh_ghl_access_token(
            refresh_token=refresh_token,
            redirect_uri=redirect_uri,
            user_type=user_type,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": "token_refresh_failed", "message": str(exc)},
            status_code=502,
        )
    user_type = str(
        token_payload.get("userType")
        or token_payload.get("user_type")
        or user_type
        or "Location"
    )
    result = _oauth_result_payload(
        token_payload,
        redirect_uri=redirect_uri,
        user_type=user_type,
    )
    try:
        result["install_store"] = await _persist_ghl_install_record(
            token_payload=token_payload,
            redirect_uri=redirect_uri,
            user_type=user_type,
            state_payload=None,
            source="oauth_refresh",
        )
    except Exception as exc:
        if LEADSMCP_MODE != DEVELOPER_MODE:
            return JSONResponse(
                {"error": "install_storage_unavailable", "message": str(exc)},
                status_code=503,
            )
        result["install_store"] = {"stored": False, "error": str(exc)}
    return JSONResponse(result)


async def _agency_installation_for_event(
    company_id: str,
) -> dict[str, Any] | None:
    candidates = await list_installations(company_id=company_id)
    agency = next(
        (
            record
            for record in candidates
            if str(record.get("user_type") or "").lower() == "company"
            and not str(record.get("location_id") or "").strip()
        ),
        None,
    )
    if agency:
        return agency
    if company_id:
        return None
    all_active = await list_installations()
    future_agencies = [
        record
        for record in all_active
        if str(record.get("user_type") or "").lower() == "company"
        and record.get("install_to_future_locations") is True
    ]
    return future_agencies[0] if len(future_agencies) == 1 else None


@orchestrator.custom_route("/webhooks/ghl", methods=["POST"])
async def ghl_marketplace_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    signature = request.headers.get("x-ghl-signature", "").strip()
    if not verify_ghl_signature(raw_body, signature):
        return JSONResponse({"error": "invalid_signature"}, status_code=401)
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "invalid_payload"}, status_code=400)

    expected_app_id = os.getenv("GHL_APP_ID", "").strip()
    app_id = str(payload.get("appId") or "").strip()
    if expected_app_id and not hmac.compare_digest(app_id, expected_app_id):
        return JSONResponse({"error": "invalid_app"}, status_code=403)

    event_id = webhook_event_id(payload, raw_body)
    existing_event = await get_webhook_event(event_id)
    if existing_event and existing_event.get("status") == "processed":
        return JSONResponse({"ok": True, "duplicate": True})

    event_type = str(payload.get("type") or "").strip().upper()
    company_id = str(payload.get("companyId") or "").strip()
    location_id = str(payload.get("locationId") or "").strip()
    status = "processed"
    processing_error = ""
    details: dict[str, Any] = {}
    try:
        if event_type == "INSTALL":
            if location_id:
                installation = await get_installation(
                    location_id=location_id,
                )
                if installation:
                    await patch_installations(
                        location_id=location_id,
                        values={
                            "installed": True,
                            "app_id": app_id or installation.get("app_id"),
                            "plan_id": str(payload.get("planId") or ""),
                            "trial": payload.get("trial"),
                            "webhook_id": event_id,
                            "uninstalled_at": None,
                        },
                    )
                    details["location_status"] = "updated"
                else:
                    agency = await _agency_installation_for_event(company_id)
                    if not agency:
                        raise RuntimeError(
                            "No agency installation is available for location-token exchange."
                        )
                    agency_token = _decrypt_from_store(
                        str(agency.get("access_token_encrypted") or "")
                    )
                    location_token = await exchange_location_token(
                        agency_access_token=agency_token,
                        company_id=str(agency.get("company_id") or company_id),
                        location_id=location_id,
                    )
                    location_token["appId"] = app_id
                    location_token["planId"] = payload.get("planId")
                    location_token["trial"] = payload.get("trial")
                    await _persist_ghl_install_record(
                        token_payload=location_token,
                        redirect_uri=str(agency.get("redirect_uri") or ""),
                        user_type="Location",
                        state_payload=None,
                        source="app_install_webhook",
                    )
                    details["location_status"] = "provisioned"
            else:
                details["agency_status"] = "awaiting_oauth_callback"
        elif event_type == "UNINSTALL":
            removed = await mark_uninstalled(
                company_id=company_id,
                location_id=location_id,
            )
            details["installations_disabled"] = removed
        elif event_type == "APP_PAYMENT_STATUS":
            updated = await patch_installations(
                company_id=company_id,
                location_id=location_id,
                values={
                    "payment_status": str(
                        payload.get("newStatus") or "PENDING"
                    ),
                    "webhook_id": event_id,
                },
            )
            details["installations_updated"] = updated
        else:
            details["ignored"] = True
    except Exception as exc:
        status = "pending"
        processing_error = str(exc)[:500]

    await record_webhook_event(
        {
            "webhook_id": event_id,
            "event_type": event_type or "UNKNOWN",
            "app_id": app_id or None,
            "company_id": company_id or None,
            "location_id": location_id or None,
            "status": status,
            "error": processing_error or None,
            "payload": payload,
        }
    )
    return JSONResponse(
        {
            "ok": status == "processed",
            "status": status,
            "details": details,
        }
    )


@orchestrator.custom_route(
    "/marketplace/billing/charge",
    methods=["POST"],
)
async def marketplace_wallet_charge(request: Request) -> JSONResponse:
    installation = getattr(request.state, "ghl_installation", None)
    if not installation:
        return JSONResponse(
            {
                "error": "installation_required",
                "message": "A bound Marketplace installation is required.",
            },
            status_code=403,
        )
    body = await _read_request_body(request)
    event_id = str(body.get("event_id") or "").strip()
    description = str(body.get("description") or "").strip()
    units = _coerce_int(body.get("units"), 0) or 0
    if not event_id or not description or units <= 0:
        return JSONResponse(
            {
                "error": "invalid_request",
                "message": "event_id, description, and units > 0 are required.",
            },
            status_code=400,
        )
    if not os.getenv("GHL_APP_ID", "").strip() or not os.getenv(
        "GHL_MARKETPLACE_METER_ID", ""
    ).strip():
        return JSONResponse(
            {
                "error": "marketplace_billing_not_configured",
                "message": "GHL_APP_ID and GHL_MARKETPLACE_METER_ID are required.",
            },
            status_code=503,
        )
    existing = await get_wallet_charge(event_id)
    if existing and existing.get("status") == "complete":
        return JSONResponse(
            {
                "ok": True,
                "duplicate": True,
                "charge_id": existing.get("charge_id"),
            }
        )

    install_key = str(installation.get("install_key") or "")
    ledger = {
        "event_id": event_id,
        "install_key": install_key,
        "status": "pending",
        "units": units,
        "description": description,
        "payload": body,
        "error": None,
    }
    await upsert_wallet_charge(ledger)
    try:
        result = await create_wallet_charge(
            access_token=_decrypt_from_store(
                str(installation.get("access_token_encrypted") or "")
            ),
            app_id=str(
                installation.get("app_id")
                or os.getenv("GHL_APP_ID", "")
            ),
            meter_id=os.getenv("GHL_MARKETPLACE_METER_ID", "").strip(),
            event_id=event_id,
            location_id=str(installation.get("location_id") or ""),
            company_id=str(installation.get("company_id") or ""),
            user_id=str(installation.get("user_id") or ""),
            description=description,
            units=units,
            price=(
                float(body["price"])
                if body.get("price") is not None
                else None
            ),
            event_time=str(body.get("event_time") or ""),
        )
    except Exception as exc:
        await upsert_wallet_charge(
            {
                **ledger,
                "status": "failed",
                "error": str(exc)[:500],
            }
        )
        return JSONResponse(
            {"error": "wallet_charge_failed", "message": str(exc)},
            status_code=502,
        )
    await upsert_wallet_charge(
        {
            **ledger,
            "status": "complete",
            "charge_id": str(result.get("chargeId") or ""),
            "error": None,
        }
    )
    return JSONResponse(
        {
            "ok": True,
            "charge_id": result.get("chargeId"),
            "event_id": event_id,
        },
        status_code=201,
    )

# ── Public support pages ─────────────────────────────────────────────────────
@orchestrator.custom_route("/support", methods=["GET"])
@orchestrator.custom_route("/support/", methods=["GET"])
async def support_page(request: Request) -> HTMLResponse:
    base_url = _public_base_url(request)
    install_url = os.getenv("GHL_OAUTH_INSTALL_URL", "").strip()
    github_url = os.getenv("LEADSMCP_GITHUB_URL", "https://github.com/dofski/leadsmcp").strip()
    return HTMLResponse(
        build_support_page(
            base_url=base_url,
            install_url=install_url,
            github_url=github_url,
        )
    )


@orchestrator.custom_route("/contact", methods=["GET"])
@orchestrator.custom_route("/contact/", methods=["GET"])
async def contact_page(request: Request) -> HTMLResponse:
    base_url = _public_base_url(request)
    install_url = os.getenv("GHL_OAUTH_INSTALL_URL", "").strip()
    github_url = os.getenv("LEADSMCP_GITHUB_URL", "https://github.com/dofski/leadsmcp").strip()
    return HTMLResponse(
        build_contact_page(
            base_url=base_url,
            github_url=github_url,
            install_url=install_url,
        )
    )


@orchestrator.custom_route("/app-install-successfully", methods=["GET"])
@orchestrator.custom_route("/app-install-successfully/", methods=["GET"])
async def install_success_page(request: Request) -> HTMLResponse:
    base_url = _public_base_url(request)
    install_url = os.getenv("GHL_OAUTH_INSTALL_URL", "").strip()
    github_url = os.getenv("LEADSMCP_GITHUB_URL", "https://github.com/dofski/leadsmcp").strip()
    webhook_url = os.getenv("LEADSMCP_INSTALL_WEBHOOK_URL", "https://hook.integrator.boost.space/5a408dz2pofunbwm82iv2ybi7mou89md").strip()
    return HTMLResponse(
        build_install_success_page(
            base_url=base_url,
            github_url=github_url,
            install_url=install_url,
            webhook_url=webhook_url,
        )
    )




# Content-Security-Policy for the GoHighLevel Marketplace onboarding page. The
# page is embedded in HighLevel's iframe, so it must permit HighLevel origins as
# frame-ancestors and must NOT emit X-Frame-Options DENY/SAMEORIGIN.




























# ══════════════════════════════════════════════════════════════════════════════
# Custom Connector OAuth 2.0 / DCR Authorization Server
# Lets ChatGPT and Perplexity (and any RFC 6749/8414/7591/9728 client) install the
# /mcp endpoint. Storage is Supabase-backed (see connector_oauth.py). Legacy
# x-mcp-secret auth continues to work in parallel.
# ══════════════════════════════════════════════════════════════════════════════
async def _read_request_body(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            parsed = await request.json()
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    try:
        form = await request.form()
    except Exception:
        return {}
    return {k: str(v) for k, v in form.items()}


def _connector_store_error(exc: "connector_oauth.StoreError") -> JSONResponse:
    """Turn a backend StoreError into a structured, non-secret 503 (never a bare 500).

    Surfaces the upstream PostgREST status and short message (e.g. "permission
    denied for table connector_oauth") so the failure is debuggable without
    Vercel logs. Contains no credentials or Supabase URL.
    """
    return JSONResponse(
        {
            "error": "temporarily_unavailable",
            "error_description": "The connector store rejected the request.",
            "store_status": exc.status,
            "store_detail": exc.detail,
        },
        status_code=503,
    )


@orchestrator.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
async def connector_oauth_as_metadata(request: Request) -> JSONResponse:
    return JSONResponse(connector_oauth.authorization_server_metadata(_public_base_url(request)))


@orchestrator.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def connector_oauth_pr_metadata(request: Request) -> JSONResponse:
    return JSONResponse(connector_oauth.protected_resource_metadata(_public_base_url(request)))


@orchestrator.custom_route("/.well-known/mcp.json", methods=["GET"])
async def connector_mcp_manifest(request: Request) -> JSONResponse:
    base = _public_base_url(request).rstrip("/")
    return JSONResponse({
        "schema_version": "1.0",
        "name_for_human": "LeadsMCP",
        "name_for_model": "leadsmcp",
        "description_for_human": "Live lead search, Google Maps business data, and GoHighLevel CRM sync in one MCP server.",
        "description_for_model": "Search for businesses and leads via Outscraper/Google Maps and push contacts and opportunities into GoHighLevel CRM. Requires OAuth authentication.",
        "auth": {
            "type": "oauth",
            "authorization_url": f"{base}/authorize",
            "token_url": f"{base}/token",
            "scope": " ".join(connector_oauth.scopes_supported()),
        },
        "api": {"type": "mcp", "url": f"{base}/mcp"},
        "contact_email": os.getenv("LEADSMCP_CONTACT_EMAIL", "") or None,
        "legal_info_url": f"{base}/support",
    })


@orchestrator.custom_route("/register", methods=["POST"])
async def connector_oauth_register(request: Request) -> JSONResponse:
    if not connector_oauth.dcr_enabled():
        return JSONResponse(
            {"error": "access_denied", "error_description": "Dynamic client registration is disabled."},
            status_code=403,
        )
    body = await _read_request_body(request)
    try:
        status, payload = await connector_oauth.register_client(body)
    except connector_oauth.StoreError as exc:
        return _connector_store_error(exc)
    return JSONResponse(payload, status_code=status)


@orchestrator.custom_route("/authorize", methods=["GET"])
@orchestrator.custom_route("/oauth/connector/authorize", methods=["GET"])
async def connector_oauth_authorize(request: Request) -> Response:
    q = request.query_params
    response_type = q.get("response_type", "code").strip()
    client_id = q.get("client_id", "").strip()
    redirect_uri = q.get("redirect_uri", "").strip()
    state = q.get("state", "").strip()
    scope = q.get("scope", "").strip() or " ".join(connector_oauth.scopes_supported())
    code_challenge = q.get("code_challenge", "").strip()
    code_challenge_method = q.get("code_challenge_method", "plain").strip() or "plain"

    if response_type != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)

    try:
        client = await connector_oauth.resolve_client(client_id)
    except connector_oauth.StoreError as exc:
        return _connector_store_error(exc)
    if not client:
        return JSONResponse(
            {"error": "invalid_client", "error_description": f"Unknown client_id: {client_id!r}."},
            status_code=400,
        )
    if not redirect_uri:
        return JSONResponse({"error": "invalid_request", "error_description": "redirect_uri is required."}, status_code=400)
    if not connector_oauth.redirect_uri_registered(client, redirect_uri):
        return JSONResponse({"error": "invalid_request", "error_description": "redirect_uri not registered for this client."}, status_code=400)

    installation_binding: dict[str, str] = {}
    cookie_value = request.cookies.get(_installation_cookie_name(), "")
    if cookie_value:
        try:
            cookie_payload = _verify_installation_cookie(cookie_value)
            installation = await get_installation(
                install_key=str(cookie_payload["install_key"])
            )
        except (ValueError, KeyError):
            installation = None
    else:
        installation = None

    if LEADSMCP_MODE != DEVELOPER_MODE and not installation:
        return JSONResponse(
            {
                "error": "installation_required",
                "error_description": (
                    "Install LeadsMCP in the CRM before authorizing an AI connector."
                ),
            },
            status_code=403,
        )

    if installation:
        if not str(installation.get("location_id") or "").strip():
            requested_location = q.get("location_id", "").strip()
            locations = [
                record
                for record in await list_installations(
                    company_id=str(installation.get("company_id") or "")
                )
                if str(record.get("location_id") or "").strip()
            ]
            if requested_location:
                installation = next(
                    (
                        record
                        for record in locations
                        if str(record.get("location_id") or "")
                        == requested_location
                    ),
                    None,
                )
            elif len(locations) == 1:
                installation = locations[0]
            else:
                return JSONResponse(
                    {
                        "error": "location_id_required",
                        "error_description": (
                            "Choose one authorized CRM business account."
                        ),
                        "available_locations": [
                            str(record.get("location_id") or "")
                            for record in locations
                        ],
                    },
                    status_code=400,
                )
        if not installation:
            return JSONResponse(
                {
                    "error": "invalid_location",
                    "error_description": "Requested location is not authorized.",
                },
                status_code=403,
            )
        installation_binding = {
            "install_key": str(installation.get("install_key") or ""),
            "company_id": str(installation.get("company_id") or ""),
            "location_id": str(installation.get("location_id") or ""),
        }

    scopes = [s for s in scope.split() if s]
    try:
        code = await connector_oauth.issue_code(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            installation=installation_binding,
        )
    except connector_oauth.StoreError as exc:
        return _connector_store_error(exc)
    params: dict[str, str] = {"code": code}
    if state:
        params["state"] = state
    return RedirectResponse(url=_append_query_params(redirect_uri, params), status_code=302)


def _extract_client_credentials(request: Request, body: dict[str, Any]) -> tuple[str, str]:
    """Resolve client_id / client_secret from Basic auth or POST body."""
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
            cid, _, csecret = decoded.partition(":")
            if cid:
                return cid.strip(), csecret.strip()
        except Exception:
            pass
    return body.get("client_id", "").strip(), body.get("client_secret", "").strip()


@orchestrator.custom_route("/token", methods=["POST"])
@orchestrator.custom_route("/oauth/connector/token", methods=["POST"])
async def connector_oauth_token(request: Request) -> JSONResponse:
    body = await _read_request_body(request)
    grant_type = body.get("grant_type", "").strip()
    client_id, client_secret = _extract_client_credentials(request, body)

    try:
        return await _connector_oauth_token_grant(request, body, grant_type, client_id, client_secret)
    except connector_oauth.StoreError as exc:
        return _connector_store_error(exc)


async def _connector_oauth_token_grant(
    request: Request,
    body: dict[str, Any],
    grant_type: str,
    client_id: str,
    client_secret: str,
) -> JSONResponse:
    client = await connector_oauth.resolve_client(client_id)
    if not client:
        return JSONResponse({"error": "invalid_client", "error_description": "Unknown client."}, status_code=401)

    # Confidential clients must present a valid secret; public clients rely on PKCE.
    is_public = client.get("token_endpoint_auth_method") == "none"
    if not is_public and not connector_oauth.validate_client_secret(client, client_secret):
        return JSONResponse({"error": "invalid_client", "error_description": "Invalid client credentials."}, status_code=401)

    if grant_type == "authorization_code":
        code = body.get("code", "").strip()
        redirect_uri = body.get("redirect_uri", "").strip()
        code_verifier = body.get("code_verifier", "").strip()
        if not code:
            return JSONResponse({"error": "invalid_request", "error_description": "code is required."}, status_code=400)

        record = await connector_oauth.consume_code(code=code)
        if not record or record.get("client_id") != client_id:
            return JSONResponse({"error": "invalid_grant", "error_description": "Code invalid, expired, or already used."}, status_code=400)

        data = record.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                data = {}
        if redirect_uri and data.get("redirect_uri") != redirect_uri:
            return JSONResponse({"error": "invalid_grant", "error_description": "redirect_uri mismatch."}, status_code=400)

        challenge = data.get("code_challenge", "")
        if (is_public or challenge) and not connector_oauth.verify_pkce(
            code_verifier=code_verifier,
            code_challenge=challenge,
            method=data.get("code_challenge_method", "plain"),
        ):
            return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed."}, status_code=400)

        scopes = data.get("scopes", []) or ["mcp"]
        installation = data.get("installation") or {}
        issued = await connector_oauth.issue_token(
            client_id=client_id,
            scopes=scopes,
            installation=installation,
        )
        return JSONResponse({
            "access_token": issued["access_token"],
            "refresh_token": issued["refresh_token"],
            "token_type": "Bearer",
            "expires_in": connector_oauth.token_ttl(),
            "scope": " ".join(scopes),
        })

    if grant_type == "refresh_token":
        refresh_token = body.get("refresh_token", "").strip()
        if not refresh_token:
            return JSONResponse({"error": "invalid_request", "error_description": "refresh_token is required."}, status_code=400)
        record = await connector_oauth.find_refresh_record(refresh_token=refresh_token)
        if not record or record.get("client_id") != client_id:
            return JSONResponse({"error": "invalid_grant", "error_description": "Refresh token invalid or expired."}, status_code=400)

        data = record.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                data = {}
        scopes = data.get("scopes", []) or ["mcp"]
        installation = data.get("installation") or {}
        issued = await connector_oauth.issue_token(
            client_id=client_id,
            scopes=scopes,
            installation=installation,
        )
        return JSONResponse({
            "access_token": issued["access_token"],
            "refresh_token": issued["refresh_token"],
            "token_type": "Bearer",
            "expires_in": connector_oauth.token_ttl(),
            "scope": " ".join(scopes),
        })

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


# RFC 8414 / RFC 9728 path-suffixed discovery variants. Spec-2025-06-18 MCP
# clients (Perplexity, Claude, ChatGPT) derive discovery URLs by inserting the
# resource path ("/mcp") after the well-known prefix, so serve identical
# metadata for any suffix instead of 401ing.
@orchestrator.custom_route("/.well-known/oauth-authorization-server/{suffix:path}", methods=["GET"])
async def connector_oauth_as_metadata_suffixed(request: Request) -> JSONResponse:
    return JSONResponse(connector_oauth.authorization_server_metadata(_public_base_url(request)))


@orchestrator.custom_route("/.well-known/oauth-protected-resource/{suffix:path}", methods=["GET"])
async def connector_oauth_pr_metadata_suffixed(request: Request) -> JSONResponse:
    return JSONResponse(connector_oauth.protected_resource_metadata(_public_base_url(request)))


# Some clients fall back to OpenID Connect discovery; serve the OAuth AS
# metadata there too (root, path-suffixed, and path-prefixed variants).
@orchestrator.custom_route("/.well-known/openid-configuration", methods=["GET"])
@orchestrator.custom_route("/.well-known/openid-configuration/{suffix:path}", methods=["GET"])
@orchestrator.custom_route("/mcp/.well-known/openid-configuration", methods=["GET"])
@orchestrator.custom_route("/mcp/.well-known/oauth-authorization-server", methods=["GET"])
async def connector_oidc_metadata(request: Request) -> JSONResponse:
    return JSONResponse(connector_oauth.authorization_server_metadata(_public_base_url(request)))


@orchestrator.custom_route("/mcp/.well-known/oauth-protected-resource", methods=["GET"])
async def connector_pr_metadata_prefixed(request: Request) -> JSONResponse:
    return JSONResponse(connector_oauth.protected_resource_metadata(_public_base_url(request)))


# ── Health check ──────────────────────────────────────────────────────────────
@orchestrator.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    app_id_configured = bool(os.getenv("GHL_APP_ID", "").strip())
    success_redirect_configured = bool(
        os.getenv("GHL_OAUTH_SUCCESS_REDIRECT_URL", "").strip()
    )
    marketplace_meter_configured = bool(
        os.getenv("GHL_MARKETPLACE_METER_ID", "").strip()
    )
    durable_oauth_ready = bool(
        ghl_install_supabase_configured()
        and connector_oauth._supabase_configured()
    )
    return JSONResponse({
        "status": "healthy",
        "services": ["outscraper", "ghl", "stripe", "tempmail"],
        "ghl_mode": "tenant-headers-with-env-fallback",
        "ghl_default_fallback_enabled": bool(DEFAULT_GHL_TOKEN and DEFAULT_GHL_LOCATION),
        "meter_event_name": os.getenv("STRIPE_METER_EVENT_NAME", "qualified_lead_export"),
        "billing_consent_mode": os.getenv("BILLING_CONSENT_MODE", "per_batch"),
        "billing_require_export_batch_id": _truthy(os.getenv("BILLING_REQUIRE_EXPORT_BATCH_ID", "true")),
        "stripe_enforce_export_access_check": _truthy(os.getenv("STRIPE_ENFORCE_EXPORT_ACCESS_CHECK", "true")),
        "qualified_lead_unit_price_usd": os.getenv("QUALIFIED_LEAD_UNIT_PRICE_USD", "1.20"),
        "auth_required": bool(os.getenv("MCP_SECRET", "").strip()),
        "ghl_oauth_configured": bool(
            os.getenv("GHL_CLIENT_ID", "").strip()
            and os.getenv("GHL_CLIENT_SECRET", "").strip()
            and os.getenv("GHL_OAUTH_REDIRECT_URI", "").strip()
            and os.getenv("GHL_OAUTH_INSTALL_URL", "").strip()
        ),
        "ghl_oauth_success_redirect_configured": success_redirect_configured,
        "ghl_callback_token_response_enabled": _allow_callback_token_response(),
        "ghl_app_id_configured": app_id_configured,
        "ghl_webhook_signature_verification": "ed25519",
        "ghl_marketplace_meter_configured": marketplace_meter_configured,
        "leadsmcp_mode": LEADSMCP_MODE,
        "ghl_install_supabase_configured": ghl_install_supabase_configured(),
        "ghl_install_store_backend": (
            install_store_backend()
            if LEADSMCP_MODE == DEVELOPER_MODE or ghl_install_supabase_configured()
            else "unavailable"
        ),
        "connector_oauth_enabled": connector_oauth.connector_oauth_enabled(),
        "connector_dcr_enabled": connector_oauth.dcr_enabled(),
        "connector_oauth_backend": (
            "supabase"
            if connector_oauth._supabase_configured()
            else (
                "unavailable"
                if connector_oauth._durable_store_required()
                else "memory"
            )
        ),
        "production_ready": bool(
            durable_oauth_ready
            and app_id_configured
            and success_redirect_configured
            and marketplace_meter_configured
            and not _allow_callback_token_response()
        ),
        "endpoint": "/mcp",
    })

@orchestrator.custom_route("/", methods=["GET"])
async def root(request: Request) -> HTMLResponse:
    base_url = _public_base_url(request)
    install_url = os.getenv("GHL_OAUTH_INSTALL_URL", "").strip()
    github_url = os.getenv("LEADSMCP_GITHUB_URL", "https://github.com/dofski/leadsmcp").strip()
    canonical_url = base_url.rstrip("/")
    return HTMLResponse(
        build_landing_page(
            base_url=base_url,
            install_url=install_url,
            github_url=github_url,
            canonical_url=canonical_url,
        )
    )

# ── ASGI app with CORS ────────────────────────────────────────────────────────
middleware = [
    Middleware(MCPSecretMiddleware),
    Middleware(
        CORSMiddleware,
        allow_origins=_cors_allowed_origins(),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "Authorization",
            "Content-Type",
            "locationId",
            "locationid",
            "x-mcp-secret",
            "x-ghl-token",
            "x-ghl-location-id",
            "x-ghl-version",
        ],
        expose_headers=["mcp-session-id"],
    )
]

app = orchestrator.http_app(middleware=middleware, stateless_http=True)

# ── Dev entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        log_level="info",
    )
