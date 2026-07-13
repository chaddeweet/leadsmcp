"""
MCP Orchestrator — Single cloud endpoint aggregating multiple services.

Services mounted:
  outscraper_*  →  Outscraper API (Google Maps, email/phone validation, enrichment)
  ghl_*         →  GoHighLevel native MCP (contacts, opportunities, pipelines)
  stripe_*      →  Stripe billing (qualified lead analysis, consent gating, metering)

Start locally:   python3 main.py
MCP endpoint:    http://localhost:8000/mcp
Health check:    http://localhost:8000/health
"""
import contextlib
import base64
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
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP, Client
from fastmcp.client.transports.http import StreamableHttpTransport
from fastmcp.server import create_proxy
from fastmcp.server.dependencies import get_http_headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.requests import Request

from servers import outscraper_server as outscraper_tools
from servers.outscraper_server import mcp as outscraper_mcp
from servers.stripe_server import mcp as stripe_mcp
from support_pages import build_marketplace_search_page
from ghl_tools import GHLToolAllowlistMiddleware


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
    """Require x-mcp-secret for non-public routes when MCP_SECRET is configured."""

    async def dispatch(self, request: Request, call_next):
        required_secret = os.getenv("MCP_SECRET", "").strip()
        if not required_secret:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in {
            "/",
            "/health",
            "/support",
            "/support/",
            "/contact",
            "/contact/",
            "/app-install-successfully",
            "/app-install-successfully/",
            "/app/lead-search",
            "/app/lead-search/",
            "/app/onboarding",
            "/app/onboarding/",
            "/api/marketplace/user-context",
            "/api/marketplace/lead-search",
            "/api/marketplace/llm-chat",
            "/api/onboarding-chat",
            "/oauth/ghl/start",
            "/oauth/ghl/callback",
            "/leadsmcp/install",
            "/leadsmcp-install",
            "/leadsmcp-install/",
        }:
            return await call_next(request)

        provided_secret = request.headers.get("x-mcp-secret", "").strip()
        if not provided_secret or provided_secret != required_secret:
            return JSONResponse(
                {
                    "error": "Unauthorized",
                    "message": "Missing or invalid x-mcp-secret header.",
                },
                status_code=401,
            )
        return await call_next(request)


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

        tenant_headers: dict[str, str] = {}

        ghl_token = incoming_headers.get("x-ghl-token") or incoming_headers.get("authorization")
        if ghl_token:
            normalized_token = ghl_token.strip()
            if normalized_token and not normalized_token.lower().startswith("bearer "):
                normalized_token = f"Bearer {normalized_token}"
            if normalized_token:
                tenant_headers["authorization"] = normalized_token

        ghl_location = incoming_headers.get("x-ghl-location-id") or incoming_headers.get("locationid")
        if ghl_location:
            tenant_headers["locationid"] = ghl_location.strip()

        ghl_version = incoming_headers.get("x-ghl-version") or incoming_headers.get("version")
        if ghl_version:
            tenant_headers["version"] = ghl_version.strip()

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


def _persist_ghl_install_record(
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

    encrypted_refresh = _encrypt_for_store(refresh_token) if refresh_token else ""
    access_fingerprint = hashlib.sha256(access_token.encode("utf-8")).hexdigest() if access_token else ""
    install_key = f"{company_id}:{location_id}" if company_id or location_id else ""

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
        "refresh_token_encrypted": encrypted_refresh,
    }

    path = _install_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    return {
        "stored": True,
        "store_path": str(path),
        "install_key": install_key or None,
        "location_id": str(location_id or ""),
        "company_id": str(company_id or ""),
    }


def _allow_callback_token_response() -> bool:
    if not _is_production_env():
        return True
    return _truthy(os.getenv("GHL_OAUTH_ALLOW_TOKEN_RESPONSE_IN_PRODUCTION", "false"))


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


def _ghl_app_shared_secret() -> str:
    return os.getenv("GHL_APP_SHARED_SECRET", "").strip()


def _openssl_evp_bytes_to_key(secret: bytes, salt: bytes, *, key_len: int, iv_len: int) -> tuple[bytes, bytes]:
    derived = b""
    block = b""
    while len(derived) < key_len + iv_len:
        block = hashlib.md5(block + secret + salt).digest()
        derived += block
    return derived[:key_len], derived[key_len : key_len + iv_len]


def _decrypt_marketplace_user_context(encrypted_data: str) -> dict[str, Any]:
    shared_secret = _ghl_app_shared_secret()
    if not shared_secret:
        raise ValueError("GHL_APP_SHARED_SECRET is not configured.")

    payload = str(encrypted_data or "").strip()
    if not payload:
        raise ValueError("Missing encryptedData.")

    try:
        blob = base64.b64decode(payload)
    except Exception as exc:
        raise ValueError("Invalid encryptedData payload.") from exc

    if not blob.startswith(b"Salted__") or len(blob) <= 16:
        raise ValueError("Unsupported encryptedData format.")

    salt = blob[8:16]
    ciphertext = blob[16:]
    key, iv = _openssl_evp_bytes_to_key(
        shared_secret.encode("utf-8"),
        salt,
        key_len=32,
        iv_len=16,
    )
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = sym_padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    try:
        parsed = json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Failed to decode decrypted user context.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Marketplace user context was not a JSON object.")
    return parsed


def _marketplace_user_context_summary(user_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "userId": str(user_context.get("userId") or "").strip(),
        "companyId": str(user_context.get("companyId") or "").strip(),
        "activeLocation": str(
            user_context.get("activeLocation")
            or user_context.get("locationId")
            or ""
        ).strip(),
        "type": str(user_context.get("type") or "").strip(),
        "role": str(user_context.get("role") or "").strip(),
        "userName": str(user_context.get("userName") or "").strip(),
        "email": str(user_context.get("email") or "").strip(),
        "versionId": str(user_context.get("versionId") or "").strip(),
        "appStatus": str(user_context.get("appStatus") or "").strip(),
        "isAgencyOwner": bool(user_context.get("isAgencyOwner")),
    }


def _marketplace_llm_model() -> str:
    configured = os.getenv("LEADSMCP_MARKETPLACE_LLM_MODEL", "").strip()
    if configured:
        return configured

    provider = _marketplace_llm_provider()
    if provider == "google":
        return "gemini-2.5-flash"
    if provider == "groq":
        return "openai/gpt-oss-20b"
    return "gpt-4o-mini"


def _marketplace_llm_provider() -> str:
    configured = os.getenv("LEADSMCP_MARKETPLACE_LLM_PROVIDER", "").strip().lower()
    if configured in {"groq", "openai", "google", "gemini"}:
        return "google" if configured == "gemini" else configured

    if os.getenv("GEMINI_API_KEY", "").strip():
        return "google"

    if os.getenv("GROQ_API_KEY", "").strip():
        return "groq"
    if os.getenv("OPENAI_API_KEY", "").strip():
        return "openai"
    return "groq"


def _marketplace_llm_config() -> dict[str, str]:
    provider = _marketplace_llm_provider()
    model = _marketplace_llm_model()

    if provider == "google":
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured for this deployment yet.")
        return {
            "provider": "google",
            "model": model,
            "api_key": api_key,
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        }

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured for this deployment yet.")
        return {
            "provider": "groq",
            "model": model,
            "api_key": api_key,
            "base_url": "https://api.groq.com/openai/v1",
        }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured for this deployment yet.")
    return {
        "provider": "openai",
        "model": model,
        "api_key": api_key,
        "base_url": "",
    }


def _coerce_marketplace_chat_messages(raw_messages: Any) -> list[dict[str, str]]:
    if not isinstance(raw_messages, list):
        raise ValueError("Request JSON must include a messages array.")

    cleaned: list[dict[str, str]] = []
    for item in raw_messages[-12:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        cleaned.append({"role": role, "content": content[:6000]})

    if not cleaned:
        raise ValueError("Provide at least one user or assistant message.")
    return cleaned


async def _marketplace_llm_headers(user_context: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}

    mcp_secret = os.getenv("MCP_SECRET", "").strip()
    if mcp_secret:
        headers["x-mcp-secret"] = mcp_secret

    location_id = str(
        user_context.get("activeLocation")
        or user_context.get("locationId")
        or ""
    ).strip()
    if location_id:
        headers["x-ghl-location-id"] = location_id

    ghl_version = os.getenv("GHL_API_VERSION", "2021-07-28").strip()
    if ghl_version:
        headers["x-ghl-version"] = ghl_version

    default_token = os.getenv("GHL_PIT_TOKEN", "").strip()
    if default_token:
        headers["x-ghl-token"] = default_token
        return headers

    install_record = _latest_install_record(
        location_id=location_id,
        company_id=str(user_context.get("companyId") or "").strip(),
    )
    if not install_record:
        return headers

    encrypted_refresh = str(install_record.get("refresh_token_encrypted") or "").strip()
    if not encrypted_refresh:
        return headers

    refresh_token = _decrypt_from_store(encrypted_refresh)
    refreshed = await _refresh_ghl_access_token(
        refresh_token=refresh_token,
        redirect_uri=str(install_record.get("redirect_uri") or _required_env("GHL_OAUTH_REDIRECT_URI")).strip(),
        user_type=str(install_record.get("user_type") or "Location").strip() or "Location",
    )
    access_token = str(refreshed.get("access_token") or "").strip()
    if access_token:
        headers["x-ghl-token"] = access_token
        try:
            _persist_ghl_install_record(
                token_payload=refreshed | {
                    "companyId": install_record.get("company_id") or "",
                    "locationId": location_id or install_record.get("location_id") or "",
                    "userId": install_record.get("user_id") or "",
                },
                redirect_uri=str(install_record.get("redirect_uri") or "").strip(),
                user_type=str(install_record.get("user_type") or "Location").strip() or "Location",
                state_payload={"tenant_id": install_record.get("tenant_id"), "customer_id": install_record.get("customer_id")},
                source="marketplace_llm_refresh",
            )
        except Exception:
            pass

    return headers


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item.get("text")))
                elif item.get("content"):
                    parts.append(str(item.get("content")))
            elif item:
                parts.append(str(item))
        return "\n".join(part.strip() for part in parts if str(part).strip()).strip()
    return str(content or "").strip()


MARKETPLACE_SEARCH_TYPES: dict[str, dict[str, Any]] = {
    "google_maps_search": {
        "label": "Google Maps Business Search",
        "description": "Search businesses by niche and geography. Best fit for net-new lead discovery from map listings.",
        "handler": outscraper_tools.google_maps_search,
        "fields": [
            {
                "name": "query",
                "label": "Search Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "plumbers, Johannesburg, ZA",
                "help": "Use business type plus city, region, or country.",
                "span": 12,
            },
            {
                "name": "limit",
                "label": "Result Limit",
                "type": "number",
                "required": True,
                "default": 20,
                "min": 1,
                "max": 500,
                "help": "Maximum number of businesses to return.",
                "span": 4,
            },
            {
                "name": "language",
                "label": "Language",
                "type": "text",
                "required": True,
                "default": "en",
                "placeholder": "en",
                "help": "ISO language code.",
                "span": 4,
            },
            {
                "name": "region",
                "label": "Region",
                "type": "text",
                "required": True,
                "default": "US",
                "placeholder": "US",
                "help": "ISO country code.",
                "span": 4,
            },
            {
                "name": "enrichments",
                "label": "Enrichments",
                "type": "text",
                "required": False,
                "placeholder": "contacts_n_leads,company_insights_service",
                "help": "Optional comma-separated enrichments supported by Outscraper.",
                "span": 12,
            },
        ],
    },
    "google_maps_reviews": {
        "label": "Google Maps Reviews",
        "description": "Pull review data for a specific business or place query.",
        "handler": outscraper_tools.google_maps_reviews,
        "fields": [
            {
                "name": "query",
                "label": "Business Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "Starbucks, Manhattan, NY, USA",
                "help": "Use a business name, place query, or place identifier.",
                "span": 12,
            },
            {
                "name": "reviews_limit",
                "label": "Reviews Limit",
                "type": "number",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 250,
                "help": "How many reviews to retrieve.",
                "span": 6,
            },
            {
                "name": "sort",
                "label": "Sort",
                "type": "text",
                "required": True,
                "default": "newest",
                "placeholder": "newest",
                "help": "newest, most_relevant, highest_rating, or lowest_rating.",
                "span": 6,
            },
        ],
    },
    "emails_and_contacts": {
        "label": "Website Emails and Contacts",
        "description": "Scrape websites one domain at a time for email addresses, phones, and social links.",
        "handler": outscraper_tools.emails_and_contacts,
        "fields": [
            {
                "name": "domains",
                "label": "Domains",
                "type": "textarea",
                "required": True,
                "rows": 4,
                "placeholder": "example.com\nanotherdomain.com",
                "help": "One or more domains. Multiple domains run sequentially.",
                "span": 12,
            },
            {
                "name": "contacts_per_company",
                "label": "Contacts Per Company",
                "type": "number",
                "required": True,
                "default": 3,
                "min": 1,
                "max": 25,
                "help": "How many contacts to request for each domain.",
                "span": 6,
            },
            {
                "name": "emails_per_contact",
                "label": "Emails Per Contact",
                "type": "number",
                "required": True,
                "default": 1,
                "min": 1,
                "max": 10,
                "help": "How many emails to request per discovered contact.",
                "span": 6,
            },
        ],
    },
    "email_validator": {
        "label": "Email Validator",
        "description": "Check email deliverability, catch invalid addresses, and review validation status.",
        "handler": outscraper_tools.email_validator,
        "fields": [
            {
                "name": "emails",
                "label": "Email Addresses",
                "type": "textarea",
                "required": True,
                "rows": 4,
                "placeholder": "founder@example.com\nteam@example.org",
                "help": "One or more email addresses separated by commas, spaces, or new lines.",
                "span": 12,
            },
        ],
    },
    "phones_enricher": {
        "label": "Phone Enricher",
        "description": "Validate and enrich phone numbers with carrier, type, and ownership data.",
        "handler": outscraper_tools.phones_enricher,
        "fields": [
            {
                "name": "phones",
                "label": "Phone Numbers",
                "type": "textarea",
                "required": True,
                "rows": 4,
                "placeholder": "+14155550123\n+27113456789",
                "help": "One or more phone numbers, ideally in E.164 format.",
                "span": 12,
            },
        ],
    },
    "similarweb": {
        "label": "Similarweb Domain Intelligence",
        "description": "Pull website traffic, rankings, and audience insights for one or more domains.",
        "handler": outscraper_tools.similarweb,
        "fields": [
            {
                "name": "domains",
                "label": "Domains",
                "type": "textarea",
                "required": True,
                "rows": 4,
                "placeholder": "apple.com\ntesla.com",
                "help": "One or more domains separated by commas, spaces, or new lines.",
                "span": 12,
            },
        ],
    },
    "geocoding": {
        "label": "Geocoding",
        "description": "Convert a full address into coordinates for mapping and spatial workflows.",
        "handler": outscraper_tools.geocoding,
        "fields": [
            {
                "name": "address",
                "label": "Address",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "1600 Amphitheatre Parkway, Mountain View, CA",
                "help": "Enter one full address to geocode.",
                "span": 12,
            },
        ],
    },
    "reverse_geocoding": {
        "label": "Reverse Geocoding",
        "description": "Turn a latitude and longitude pair into a human-readable address.",
        "handler": outscraper_tools.reverse_geocoding,
        "fields": [
            {
                "name": "coordinates",
                "label": "Coordinates",
                "type": "text",
                "required": True,
                "placeholder": "37.4224764,-122.0842499",
                "help": "Provide one latitude,longitude pair.",
                "span": 12,
            },
        ],
    },
    "google_search": {
        "label": "Google Search Research",
        "description": "Run a Google web search for prospecting research or company discovery before lead enrichment.",
        "handler": outscraper_tools.google_search,
        "fields": [
            {
                "name": "query",
                "label": "Search Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "superyacht brokers in Dubai",
                "help": "General search query for prospecting research.",
                "span": 12,
            },
            {
                "name": "pages_per_query",
                "label": "Pages Per Query",
                "type": "number",
                "required": True,
                "default": 1,
                "min": 1,
                "max": 10,
                "help": "How many search result pages to retrieve.",
                "span": 4,
            },
            {
                "name": "language",
                "label": "Language",
                "type": "text",
                "required": True,
                "default": "en",
                "placeholder": "en",
                "help": "ISO language code.",
                "span": 4,
            },
            {
                "name": "region",
                "label": "Region",
                "type": "text",
                "required": True,
                "default": "US",
                "placeholder": "US",
                "help": "ISO country code.",
                "span": 4,
            },
        ],
    },
    "google_search_news": {
        "label": "Google Search News",
        "description": "Search Google News for recent articles about companies, people, and markets.",
        "handler": outscraper_tools.google_search_news,
        "fields": [
            {
                "name": "query",
                "label": "News Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "OpenAI funding news",
                "help": "Search term for news research.",
                "span": 12,
            },
            {
                "name": "pages_per_query",
                "label": "Pages Per Query",
                "type": "number",
                "required": True,
                "default": 1,
                "min": 1,
                "max": 10,
                "help": "How many news result pages to retrieve.",
                "span": 4,
            },
            {
                "name": "language",
                "label": "Language",
                "type": "text",
                "required": True,
                "default": "en",
                "placeholder": "en",
                "help": "ISO language code.",
                "span": 4,
            },
            {
                "name": "region",
                "label": "Region",
                "type": "text",
                "required": True,
                "default": "US",
                "placeholder": "US",
                "help": "ISO country code.",
                "span": 4,
            },
        ],
    },
    "google_trends": {
        "label": "Google Trends",
        "description": "Check search-interest trends for one or more terms.",
        "handler": outscraper_tools.google_trends,
        "fields": [
            {
                "name": "query",
                "label": "Trend Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "couples coaching, marriage retreat",
                "help": "One or more search terms to analyze.",
                "span": 12,
            },
            {
                "name": "language",
                "label": "Language",
                "type": "text",
                "required": True,
                "default": "en",
                "placeholder": "en",
                "help": "ISO language code.",
                "span": 6,
            },
            {
                "name": "region",
                "label": "Region",
                "type": "text",
                "required": True,
                "default": "US",
                "placeholder": "US",
                "help": "ISO country code.",
                "span": 6,
            },
        ],
    },
    "linkedin_profiles": {
        "label": "LinkedIn Profiles",
        "description": "Search or fetch LinkedIn person profiles for individual prospect research.",
        "handler": outscraper_tools.linkedin_profiles,
        "fields": [
            {
                "name": "query",
                "label": "Profile Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "https://www.linkedin.com/in/realvlad or realvlad",
                "help": "LinkedIn profile URL, username, or a focused search term.",
                "span": 12,
            },
            {
                "name": "limit",
                "label": "Result Limit",
                "type": "number",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 100,
                "help": "Maximum number of profiles to return.",
                "span": 12,
            },
        ],
    },
    "linkedin_companies": {
        "label": "LinkedIn Companies",
        "description": "Search LinkedIn company pages for account research and company discovery.",
        "handler": outscraper_tools.linkedin_companies,
        "fields": [
            {
                "name": "query",
                "label": "Company Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "https://www.linkedin.com/company/outscraper or outscraper",
                "help": "Company URL, company name, or company identifier.",
                "span": 12,
            },
            {
                "name": "limit",
                "label": "Result Limit",
                "type": "number",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 100,
                "help": "Maximum number of companies to return.",
                "span": 12,
            },
        ],
    },
    "linkedin_posts": {
        "label": "LinkedIn Posts",
        "description": "Pull posts from LinkedIn company pages for content and outreach context.",
        "handler": outscraper_tools.linkedin_posts,
        "fields": [
            {
                "name": "query",
                "label": "Company Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "https://www.linkedin.com/company/outscraper or outscraper",
                "help": "Company URL or company identifier.",
                "span": 12,
            },
            {
                "name": "limit",
                "label": "Post Limit",
                "type": "number",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 100,
                "help": "Maximum number of posts to return.",
                "span": 12,
            },
        ],
    },
    "tiktok_profiles": {
        "label": "TikTok Profiles",
        "description": "Search TikTok profiles for creator, brand, and audience research.",
        "handler": outscraper_tools.tiktok_profiles,
        "fields": [
            {
                "name": "query",
                "label": "TikTok Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "relationship coach",
                "help": "Username or search term.",
                "span": 12,
            },
            {
                "name": "limit",
                "label": "Result Limit",
                "type": "number",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 100,
                "help": "Maximum number of profiles to return.",
                "span": 12,
            },
        ],
    },
    "twitter_profiles": {
        "label": "X / Twitter Profiles",
        "description": "Search X profiles for founder, brand, and media research.",
        "handler": outscraper_tools.twitter_profiles,
        "fields": [
            {
                "name": "query",
                "label": "Profile Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "marriage coach",
                "help": "Username or search term.",
                "span": 12,
            },
            {
                "name": "limit",
                "label": "Result Limit",
                "type": "number",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 100,
                "help": "Maximum number of profiles to return.",
                "span": 12,
            },
        ],
    },
    "youtube_search": {
        "label": "YouTube Search",
        "description": "Search YouTube videos for topics, channels, and outreach research.",
        "handler": outscraper_tools.youtube_search,
        "fields": [
            {
                "name": "query",
                "label": "YouTube Query",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "relationship podcast",
                "help": "Search term for YouTube discovery.",
                "span": 12,
            },
            {
                "name": "limit",
                "label": "Result Limit",
                "type": "number",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 100,
                "help": "Maximum number of videos to return.",
                "span": 12,
            },
        ],
    },
    "youtube_videos": {
        "label": "YouTube Channel Videos",
        "description": "Pull recent videos from a specific YouTube channel.",
        "handler": outscraper_tools.youtube_videos,
        "fields": [
            {
                "name": "channel_url",
                "label": "Channel URL",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "https://www.youtube.com/@channelname",
                "help": "Channel URL, username, or channel identifier.",
                "span": 12,
            },
            {
                "name": "limit",
                "label": "Video Limit",
                "type": "number",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 100,
                "help": "Maximum number of videos to return.",
                "span": 12,
            },
        ],
    },
    "youtube_transcripts": {
        "label": "YouTube Transcript",
        "description": "Fetch transcript and caption text from a YouTube video.",
        "handler": outscraper_tools.youtube_transcripts,
        "fields": [
            {
                "name": "video_url",
                "label": "Video URL",
                "type": "textarea",
                "required": True,
                "rows": 3,
                "placeholder": "https://www.youtube.com/watch?v=...",
                "help": "Provide a YouTube video URL or video ID.",
                "span": 12,
            },
        ],
    },
}


def _marketplace_search_public_config() -> dict[str, dict[str, Any]]:
    public: dict[str, dict[str, Any]] = {}
    for search_type, config in MARKETPLACE_SEARCH_TYPES.items():
        public[search_type] = {
            "label": config["label"],
            "description": config["description"],
            "fields": config["fields"],
        }
    return public


def _coerce_marketplace_search_params(search_type: str, raw_params: Any) -> dict[str, Any]:
    config = MARKETPLACE_SEARCH_TYPES.get(search_type)
    if not config:
        raise ValueError(f"Unsupported searchType '{search_type}'.")
    if raw_params is None:
        raw_params = {}
    if not isinstance(raw_params, dict):
        raise ValueError("params must be a JSON object.")

    normalized: dict[str, Any] = {}
    for field in config["fields"]:
        name = field["name"]
        value = raw_params.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            if "default" in field:
                value = field["default"]
        if field.get("required") and (value is None or (isinstance(value, str) and not value.strip())):
            raise ValueError(f"Missing required field '{name}'.")

        if field["type"] == "number":
            if value is None or value == "":
                continue
            parsed = _coerce_int(value, fallback=None)
            if parsed is None:
                raise ValueError(f"Field '{name}' must be a number.")
            min_value = field.get("min")
            max_value = field.get("max")
            if min_value is not None and parsed < int(min_value):
                raise ValueError(f"Field '{name}' must be >= {min_value}.")
            if max_value is not None and parsed > int(max_value):
                raise ValueError(f"Field '{name}' must be <= {max_value}.")
            normalized[name] = parsed
            continue

        text = str(value or "").strip()
        if text:
            normalized[name] = text

    return normalized


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    return ""


def _coerce_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _extract_domain_from_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"https://{text}"
    try:
        parsed = urlparse(text)
    except Exception:
        return ""
    host = (parsed.netloc or parsed.path or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalize_website_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("mailto:") or text.startswith("tel:"):
        return ""
    if "://" not in text:
        text = f"https://{text}"
    try:
        parsed = urlparse(text)
    except Exception:
        return ""
    host = (parsed.netloc or parsed.path or "").strip().lower()
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or ""
    normalized = urlunparse(("https", host, path.rstrip("/"), "", "", ""))
    return normalized.rstrip("/")


def _normalize_asset_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("mailto:") or text.startswith("tel:"):
        return ""
    if "://" not in text:
        text = f"https://{text}"
    try:
        parsed = urlparse(text)
    except Exception:
        return ""
    host = (parsed.netloc or parsed.path or "").strip().lower()
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return urlunparse(("https", host, parsed.path or "", parsed.params or "", parsed.query or "", parsed.fragment or ""))


def _extract_primary_email(record: dict[str, Any]) -> str:
    email = _first_non_empty(record.get("email"), record.get("business_email"))
    if email:
        return email.lower()

    email_lists = [
        record.get("emails"),
        record.get("email_addresses"),
        record.get("business_emails"),
    ]
    for value in email_lists:
        if isinstance(value, list):
            for item in value:
                found = _first_non_empty(item.get("email") if isinstance(item, dict) else item)
                if found:
                    return found.lower()
    return ""


def _extract_primary_phone(record: dict[str, Any]) -> str:
    phone = _first_non_empty(record.get("phone"), record.get("phone_number"), record.get("business_phone"))
    if phone:
        return phone

    phone_lists = [record.get("phones"), record.get("phone_numbers")]
    for value in phone_lists:
        if isinstance(value, list):
            for item in value:
                found = _first_non_empty(item.get("number") if isinstance(item, dict) else item)
                if found:
                    return found
    return ""


def _extract_coordinates(record: dict[str, Any]) -> tuple[float | None, float | None]:
    candidate_pairs: list[tuple[Any, Any]] = [
        (record.get("latitude"), record.get("longitude")),
        (record.get("lat"), record.get("lng")),
        (record.get("lat"), record.get("lon")),
        (record.get("y"), record.get("x")),
    ]

    for container_key in ("coordinates", "coordinate", "gps_coordinates", "location", "geo", "center"):
        container = record.get(container_key)
        if isinstance(container, dict):
            candidate_pairs.extend(
                [
                    (container.get("latitude"), container.get("longitude")),
                    (container.get("lat"), container.get("lng")),
                    (container.get("lat"), container.get("lon")),
                    (container.get("y"), container.get("x")),
                ]
            )

    for lat_value, lng_value in candidate_pairs:
        lat = _coerce_optional_float(lat_value)
        lng = _coerce_optional_float(lng_value)
        if lat is not None and lng is not None:
            return lat, lng
    return None, None


def _extract_marketplace_image(record: dict[str, Any]) -> str:
    image_value = _first_non_empty(
        record.get("logo"),
        record.get("logo_url"),
        record.get("logoUrl"),
        record.get("image"),
        record.get("image_url"),
        record.get("imageUrl"),
        record.get("photo"),
        record.get("photo_url"),
        record.get("photoUrl"),
        record.get("thumbnail"),
        record.get("thumbnail_url"),
        record.get("thumbnailUrl"),
        record.get("favicon"),
        record.get("icon"),
        record.get("profile_image"),
        record.get("profile_image_url"),
        record.get("company_logo"),
        record.get("company_logo_url"),
    )
    if image_value:
        return _normalize_asset_url(image_value)

    for container_key in ("images", "media", "assets", "profile", "company"):
        container = record.get(container_key)
        if isinstance(container, dict):
            nested_value = _first_non_empty(
                container.get("logo"),
                container.get("logo_url"),
                container.get("image"),
                container.get("image_url"),
                container.get("photo"),
                container.get("thumbnail"),
                container.get("favicon"),
                container.get("icon"),
            )
            if nested_value:
                return _normalize_asset_url(nested_value)
        if isinstance(container, list):
            for item in container:
                if isinstance(item, dict):
                    nested_value = _first_non_empty(
                        item.get("logo"),
                        item.get("logo_url"),
                        item.get("image"),
                        item.get("image_url"),
                        item.get("photo"),
                        item.get("thumbnail"),
                        item.get("url"),
                    )
                else:
                    nested_value = item
                normalized = _normalize_asset_url(nested_value)
                if normalized:
                    return normalized
    return ""


def _looks_like_marketplace_record(record: dict[str, Any]) -> bool:
    candidate_keys = {
        "name",
        "business_name",
        "title",
        "company_name",
        "website",
        "domain",
        "address",
        "formatted_address",
        "phone",
        "email",
        "place_id",
        "query",
        "link",
        "url",
    }
    return any(key in record for key in candidate_keys)


def _extract_marketplace_records(result: Any, fallback_domain: str = "") -> list[tuple[dict[str, Any], str]]:
    extracted: list[tuple[dict[str, Any], str]] = []

    if isinstance(result, list):
        for item in result:
            extracted.extend(_extract_marketplace_records(item, fallback_domain))
        return extracted

    if not isinstance(result, dict):
        return extracted

    if result.get("mode") == "serial_per_domain" and isinstance(result.get("results"), list):
        for entry in result["results"]:
            if not isinstance(entry, dict):
                continue
            entry_domain = _first_non_empty(entry.get("domain"), fallback_domain)
            extracted.extend(_extract_marketplace_records(entry.get("result"), entry_domain))
        return extracted

    for key in ("data", "items", "organic_results", "companies", "places", "contacts", "leads"):
        nested = result.get(key)
        if isinstance(nested, list):
            for item in nested:
                extracted.extend(_extract_marketplace_records(item, fallback_domain))
            if extracted:
                return extracted

    nested_results = result.get("results")
    if isinstance(nested_results, list):
        if nested_results and all(isinstance(item, dict) and "result" in item for item in nested_results):
            for item in nested_results:
                item_domain = _first_non_empty(item.get("domain"), fallback_domain)
                extracted.extend(_extract_marketplace_records(item.get("result"), item_domain))
        else:
            for item in nested_results:
                extracted.extend(_extract_marketplace_records(item, fallback_domain))
        if extracted:
            return extracted

    if _looks_like_marketplace_record(result):
        extracted.append((result, fallback_domain))
    return extracted


def _normalize_contact_row(
    domain_record: dict[str, Any],
    contact_record: dict[str, Any],
    *,
    search_type: str,
    fallback_domain: str = "",
) -> dict[str, Any]:
    merged = dict(domain_record)
    merged.update(contact_record)

    domain_value = _first_non_empty(
        domain_record.get("query"),
        domain_record.get("domain"),
        domain_record.get("website"),
        domain_record.get("url"),
        fallback_domain,
    )
    website = _normalize_website_value(
        _first_non_empty(
            contact_record.get("website"),
            domain_record.get("website"),
            domain_record.get("url"),
            domain_value,
        )
    )
    website_domain = _extract_domain_from_value(website or domain_value or fallback_domain)

    contact_name = _first_non_empty(
        contact_record.get("name"),
        contact_record.get("full_name"),
        contact_record.get("first_name"),
        contact_record.get("title"),
    )
    title_bits = [
        _first_non_empty(contact_record.get("job_title"), contact_record.get("position"), contact_record.get("headline")),
        _first_non_empty(contact_record.get("department"), contact_record.get("seniority")),
    ]
    title = " · ".join(bit for bit in title_bits if bit)

    primary_email = _extract_primary_email(contact_record)
    if not primary_email:
        primary_email = _extract_primary_email(domain_record)

    primary_phone = _extract_primary_phone(contact_record)
    if not primary_phone:
        primary_phone = _extract_primary_phone(domain_record)

    description = _first_non_empty(
        contact_record.get("description"),
        contact_record.get("summary"),
        contact_record.get("bio"),
        title,
        domain_record.get("description"),
    )

    display_name = contact_name or website_domain or _first_non_empty(domain_record.get("query"), "Contact Result")
    identity_seed = "|".join(
        [
            search_type,
            display_name,
            primary_email,
            primary_phone,
            website_domain,
            title,
        ]
    )

    return {
        "id": hashlib.sha1(identity_seed.encode("utf-8")).hexdigest()[:16],
        "searchType": search_type,
        "name": display_name,
        "address": _first_non_empty(domain_record.get("address"), domain_record.get("formatted_address"), domain_record.get("full_address")),
        "city": _first_non_empty(domain_record.get("city"), domain_record.get("town")),
        "state": _first_non_empty(domain_record.get("state"), domain_record.get("region")),
        "country": _first_non_empty(domain_record.get("country"), domain_record.get("country_code")),
        "postalCode": _first_non_empty(domain_record.get("postal_code"), domain_record.get("zip"), domain_record.get("postcode")),
        "phone": primary_phone,
        "email": primary_email,
        "website": website,
        "websiteDomain": website_domain,
        "domain": website_domain or fallback_domain,
        "category": _first_non_empty(contact_record.get("job_title"), contact_record.get("position"), contact_record.get("department"), domain_record.get("category")),
        "description": description,
        "sourceUrl": _normalize_website_value(_first_non_empty(contact_record.get("linkedin"), contact_record.get("url"), domain_record.get("source_url"), domain_record.get("url"))),
        "logoUrl": _extract_marketplace_image(contact_record) or _extract_marketplace_image(domain_record),
        "rating": None,
        "reviewCount": None,
        "latitude": None,
        "longitude": None,
        "hasCoordinates": False,
        "raw": merged,
    }


def _extract_contact_style_records(result: Any, fallback_domain: str = "") -> list[tuple[dict[str, Any], str]]:
    extracted: list[tuple[dict[str, Any], str]] = []

    if isinstance(result, list):
        for item in result:
            extracted.extend(_extract_contact_style_records(item, fallback_domain))
        return extracted

    if not isinstance(result, dict):
        return extracted

    if result.get("mode") == "serial_per_domain" and isinstance(result.get("results"), list):
        for entry in result["results"]:
            if not isinstance(entry, dict):
                continue
            entry_domain = _first_non_empty(entry.get("domain"), fallback_domain)
            extracted.extend(_extract_contact_style_records(entry.get("result"), entry_domain))
        return extracted

    for key in ("data", "items", "results"):
        nested = result.get(key)
        if isinstance(nested, list):
            for item in nested:
                if not isinstance(item, dict):
                    continue
                item_domain = _first_non_empty(item.get("domain"), item.get("query"), item.get("website"), fallback_domain)
                if "contacts" in item or "emails" in item or "phones" in item or item_domain:
                    extracted.append((item, item_domain or fallback_domain))
                else:
                    extracted.extend(_extract_contact_style_records(item, fallback_domain))
            if extracted:
                return extracted

    item_domain = _first_non_empty(result.get("domain"), result.get("query"), result.get("website"), fallback_domain)
    if "contacts" in result or "emails" in result or "phones" in result or item_domain:
        extracted.append((result, item_domain or fallback_domain))
    return extracted


def _extract_contact_style_marketplace_leads(search_type: str, result: Any) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for domain_record, fallback_domain in _extract_contact_style_records(result):
        contacts = domain_record.get("contacts")
        if isinstance(contacts, list) and contacts:
            for contact in contacts:
                if not isinstance(contact, dict):
                    continue
                lead = _normalize_contact_row(
                    domain_record,
                    contact,
                    search_type=search_type,
                    fallback_domain=fallback_domain,
                )
                seen.setdefault(lead["id"], lead)
            continue

        generic_emails = domain_record.get("emails") if isinstance(domain_record.get("emails"), list) else []
        generic_phones = domain_record.get("phones") if isinstance(domain_record.get("phones"), list) else []
        fallback_contact = {
            "name": _first_non_empty(domain_record.get("query"), domain_record.get("domain")),
            "email": generic_emails[0] if generic_emails else "",
            "phone": generic_phones[0] if generic_phones else "",
            "emails": generic_emails,
            "phones": generic_phones,
        }
        lead = _normalize_contact_row(
            domain_record,
            fallback_contact,
            search_type=search_type,
            fallback_domain=fallback_domain,
        )
        seen.setdefault(lead["id"], lead)
    return list(seen.values())


def _normalize_marketplace_lead(
    record: dict[str, Any],
    *,
    search_type: str,
    fallback_domain: str = "",
) -> dict[str, Any]:
    name = _first_non_empty(
        record.get("name"),
        record.get("business_name"),
        record.get("title"),
        record.get("company_name"),
        record.get("company"),
    )
    website = _normalize_website_value(
        _first_non_empty(record.get("website"), record.get("site"), record.get("url"), record.get("link"), record.get("domain"), fallback_domain)
    )
    website_domain = _extract_domain_from_value(website or fallback_domain or record.get("domain"))
    email = _extract_primary_email(record)
    phone = _extract_primary_phone(record)
    latitude, longitude = _extract_coordinates(record)
    address = _first_non_empty(
        record.get("address"),
        record.get("formatted_address"),
        record.get("full_address"),
        record.get("street"),
    )
    city = _first_non_empty(record.get("city"), record.get("town"))
    state = _first_non_empty(record.get("state"), record.get("region"))
    country = _first_non_empty(record.get("country"), record.get("country_code"))
    postal_code = _first_non_empty(record.get("postal_code"), record.get("zip"), record.get("postcode"))
    category = _first_non_empty(record.get("category"), record.get("type"), record.get("primary_category"))
    description = _first_non_empty(record.get("description"), record.get("snippet"), record.get("about"))
    source_url = _normalize_website_value(_first_non_empty(record.get("source_url"), record.get("link"), record.get("url")))
    logo_url = _extract_marketplace_image(record)
    rating = _coerce_optional_float(record.get("rating"))
    review_count = _coerce_optional_float(
        _first_non_empty(record.get("reviews"), record.get("reviews_count"), record.get("review_count"))
    )

    display_name = name or website_domain or _first_non_empty(record.get("query"), source_url, "Lead Result")
    identity_seed = "|".join(
        [
            search_type,
            display_name,
            address,
            website_domain,
            f"{latitude or ''}",
            f"{longitude or ''}",
        ]
    )

    return {
        "id": hashlib.sha1(identity_seed.encode("utf-8")).hexdigest()[:16],
        "searchType": search_type,
        "name": display_name,
        "address": address,
        "city": city,
        "state": state,
        "country": country,
        "postalCode": postal_code,
        "phone": phone,
        "email": email,
        "website": website,
        "websiteDomain": website_domain,
        "domain": website_domain or fallback_domain,
        "category": category,
        "description": description,
        "sourceUrl": source_url,
        "logoUrl": logo_url,
        "rating": rating,
        "reviewCount": int(review_count) if review_count is not None else None,
        "latitude": latitude,
        "longitude": longitude,
        "hasCoordinates": latitude is not None and longitude is not None,
        "raw": record,
    }


def _extract_marketplace_leads(search_type: str, result: Any) -> list[dict[str, Any]]:
    if search_type == "emails_and_contacts":
        return _extract_contact_style_marketplace_leads(search_type, result)
    seen: dict[str, dict[str, Any]] = {}
    for record, fallback_domain in _extract_marketplace_records(result):
        lead = _normalize_marketplace_lead(record, search_type=search_type, fallback_domain=fallback_domain)
        if lead["id"] not in seen:
            seen[lead["id"]] = lead
    return list(seen.values())


def _marketplace_map_center(leads: list[dict[str, Any]]) -> dict[str, float] | None:
    geo_leads = [lead for lead in leads if lead.get("hasCoordinates")]
    if not geo_leads:
        return None
    latitudes = [float(lead["latitude"]) for lead in geo_leads if lead.get("latitude") is not None]
    longitudes = [float(lead["longitude"]) for lead in geo_leads if lead.get("longitude") is not None]
    if not latitudes or not longitudes:
        return None
    return {
        "latitude": sum(latitudes) / len(latitudes),
        "longitude": sum(longitudes) / len(longitudes),
    }


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


def _oauth_redirect_uri(request: Request) -> str:
    configured = os.getenv("GHL_OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return str(request.url.replace(query=""))


def _oauth_user_type(fallback: str = "") -> str:
    return fallback.strip() or os.getenv("GHL_OAUTH_USER_TYPE", "Location").strip() or "Location"


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
        "user_type": user_type,
        "redirect_uri": redirect_uri,
    }
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
        "user_type": user_type,
        "redirect_uri": redirect_uri,
    }
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
""",
)

# ── Mount local Outscraper sub-server ──────────────────────────────────────────
orchestrator.mount(outscraper_mcp, namespace="outscraper")
orchestrator.mount(stripe_mcp, namespace="stripe")

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

# HighLevel v2 exposes a compact five-tool catalog that discovers hundreds of operations.
# Expose the complete v2 surface by default. The legacy lead/contact allowlist remains
# available as an opt-in compatibility mode for constrained deployments.
if os.getenv("GHL_V2_TOOL_ALLOWLIST_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
    orchestrator.add_middleware(GHLToolAllowlistMiddleware())

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

    result = _oauth_result_payload(
        token_payload,
        redirect_uri=redirect_uri,
        user_type=user_type,
        state_payload=state_payload,
    )

    store_status: dict[str, Any]
    try:
        store_status = _persist_ghl_install_record(
            token_payload=token_payload,
            redirect_uri=redirect_uri,
            user_type=user_type,
            state_payload=state_payload,
            source="oauth_callback",
        )
    except Exception as exc:
        store_status = {"stored": False, "error": str(exc)}

    success_redirect = os.getenv("GHL_OAUTH_SUCCESS_REDIRECT_URL", "").strip()
    if success_redirect:
        redirect_params = {
            "status": "connected",
            "company_id": str(result.get("company_id") or ""),
            "location_id": str(result.get("location_id") or ""),
            "user_type": str(user_type),
            "tokens_hidden": "true",
            "install_stored": "true" if store_status.get("stored") else "false",
        }
        return RedirectResponse(url=_append_query_params(success_redirect, redirect_params), status_code=303)

    if not _allow_callback_token_response():
        return JSONResponse(
            {
                "ok": True,
                "status": "connected",
                "redirect_uri": redirect_uri,
                "user_type": user_type,
                "company_id": str(result.get("company_id") or ""),
                "location_id": str(result.get("location_id") or ""),
                "tokens_hidden": True,
                "install_stored": bool(store_status.get("stored")),
            }
        )

    result["install_store"] = store_status
    return JSONResponse(result)


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
    result = _oauth_result_payload(
        token_payload,
        redirect_uri=redirect_uri,
        user_type=user_type,
    )
    try:
        result["install_store"] = _persist_ghl_install_record(
            token_payload=token_payload,
            redirect_uri=redirect_uri,
            user_type=user_type,
            state_payload=None,
            source="oauth_exchange",
        )
    except Exception as exc:
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
    result = _oauth_result_payload(
        token_payload,
        redirect_uri=redirect_uri,
        user_type=user_type,
    )
    try:
        result["install_store"] = _persist_ghl_install_record(
            token_payload=token_payload,
            redirect_uri=redirect_uri,
            user_type=user_type,
            state_payload=None,
            source="oauth_refresh",
        )
    except Exception as exc:
        result["install_store"] = {"stored": False, "error": str(exc)}
    return JSONResponse(result)

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


@orchestrator.custom_route("/app/onboarding", methods=["GET"])
@orchestrator.custom_route("/app/onboarding/", methods=["GET"])
async def onboarding_chat_page(request: Request) -> HTMLResponse:
    html_path = Path(__file__).parent / "pages" / "onboarding-chat.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@orchestrator.custom_route("/app/lead-search", methods=["GET"])
@orchestrator.custom_route("/app/lead-search/", methods=["GET"])
async def marketplace_lead_search_page(request: Request) -> HTMLResponse:
    base_url = _public_base_url(request)
    github_url = os.getenv("LEADSMCP_GITHUB_URL", "https://github.com/dofski/leadsmcp").strip()
    mapbox_public_token = os.getenv("MAPBOX_PUBLIC_TOKEN", "").strip()
    mapbox_style_url = os.getenv("MAPBOX_STYLE_URL", "mapbox://styles/mapbox/standard-satellite").strip()
    mapbox_js_url = "https://api.mapbox.com/mapbox-gl-js/v3.19.1/mapbox-gl.js"
    mapbox_css_url = "https://api.mapbox.com/mapbox-gl-js/v3.19.1/mapbox-gl.css"
    search_config_json = json.dumps(_marketplace_search_public_config(), separators=(",", ":")).replace("</", "<\\/")
    return HTMLResponse(
        build_marketplace_search_page(
            base_url=base_url,
            github_url=github_url,
            context_endpoint=f"{base_url}/api/marketplace/user-context",
            search_endpoint=f"{base_url}/api/marketplace/lead-search",
            ai_endpoint=f"{base_url}/api/marketplace/llm-chat",
            search_config_json=search_config_json,
            mapbox_public_token=mapbox_public_token,
            mapbox_style_url=mapbox_style_url,
            mapbox_js_url=mapbox_js_url,
            mapbox_css_url=mapbox_css_url,
        )
    )


@orchestrator.custom_route("/api/marketplace/user-context", methods=["POST"])
async def marketplace_user_context(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    encrypted_data = str(body.get("encryptedData") or "").strip()
    if not encrypted_data:
        return JSONResponse(
            {"ok": False, "error": "missing_encrypted_data", "message": "Request JSON must include encryptedData."},
            status_code=400,
        )

    try:
        user_context = _decrypt_marketplace_user_context(encrypted_data)
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "context_decrypt_failed", "message": str(exc)},
            status_code=400,
        )

    return JSONResponse(
        {
            "ok": True,
            "context": _marketplace_user_context_summary(user_context),
        }
    )


@orchestrator.custom_route("/api/marketplace/llm-chat", methods=["POST"])
async def marketplace_llm_chat(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    encrypted_data = str(body.get("encryptedData") or "").strip()
    raw_messages = body.get("messages") or []
    current_search = body.get("currentSearch") or {}

    if not encrypted_data:
        return JSONResponse(
            {"ok": False, "error": "missing_encrypted_data", "message": "Request JSON must include encryptedData."},
            status_code=400,
        )

    try:
        llm_config = _marketplace_llm_config()
    except ValueError as exc:
        message = str(exc)
        return JSONResponse(
            {
                "ok": False,
                "error": "missing_llm_api_key",
                "message": message,
                "provider": _marketplace_llm_provider(),
            },
            status_code=503,
        )

    try:
        user_context = _decrypt_marketplace_user_context(encrypted_data)
        messages = _coerce_marketplace_chat_messages(raw_messages)
    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "error": "invalid_request", "message": str(exc)},
            status_code=400,
        )
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "context_decrypt_failed", "message": str(exc)},
            status_code=400,
        )

    try:
        from langchain_openai import ChatOpenAI
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langgraph.prebuilt import create_react_agent
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "llm_dependencies_unavailable", "message": str(exc)},
            status_code=500,
        )

    context_summary = _marketplace_user_context_summary(user_context)
    active_location = context_summary.get("activeLocation") or "unknown"
    company_id = context_summary.get("companyId") or "unknown"

    current_search_note = ""
    if isinstance(current_search, dict) and current_search:
        preview = {
            "searchType": current_search.get("searchType"),
            "searchLabel": current_search.get("searchLabel"),
            "leadCount": current_search.get("leadCount"),
            "leadPreview": (current_search.get("leadPreview") or [])[:5],
        }
        current_search_note = f"\nCurrent workspace search context:\n{json.dumps(preview, ensure_ascii=True)}\n"

    system_prompt = f"""
You are the LeadsMCP AI workspace copilot embedded inside a GoHighLevel custom page.

Rules:
- You are connected to the same LeadsMCP MCP server backing this page.
- You may use Outscraper research tools and GoHighLevel tools.
- You may read from GoHighLevel and write to GoHighLevel when the user clearly asks you to create, update, or organize records.
- Do not use Stripe billing/export tools from this page.
- Prefer Outscraper and research tools for discovery, and GHL tools for CRM lookup, create, update, tagging, and organization.
- If the user asks about the current visible search results, use the provided workspace context first.
- Be concise, practical, and action-oriented.
- When you write to GHL, briefly summarize exactly what you changed.

Marketplace session:
- company_id: {company_id}
- active_location: {active_location}
{current_search_note}
""".strip()

    mcp_url = f"{_public_base_url(request)}/mcp"
    try:
        headers = await _marketplace_llm_headers(user_context)
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "ghl_auth_resolution_failed", "message": str(exc)},
            status_code=500,
        )

    try:
        client = MultiServerMCPClient(
            {
                "leadsmcp": {
                    "url": mcp_url,
                    "transport": "streamable_http",
                    "headers": headers,
                }
            }
        )
        tools = await client.get_tools()
        workspace_tools = [
            tool for tool in tools
            if getattr(tool, "name", "").startswith("outscraper_")
            or getattr(tool, "name", "").startswith("ghl_")
        ]

        llm_kwargs: dict[str, Any] = {
            "model": llm_config["model"],
            "api_key": llm_config["api_key"],
            "temperature": 1e-8,
        }
        if llm_config.get("base_url"):
            llm_kwargs["base_url"] = llm_config["base_url"]

        llm = ChatOpenAI(**llm_kwargs)

        agent = create_react_agent(llm, workspace_tools, prompt=system_prompt)
        result = await agent.ainvoke({"messages": messages})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "llm_run_failed", "message": str(exc)},
            status_code=500,
        )

    reply = ""
    tool_calls: list[str] = []
    for msg in result.get("messages", []):
        msg_type = getattr(msg, "type", "")
        if msg_type == "ai":
            text = _message_content_text(getattr(msg, "content", ""))
            if text:
                reply = text
            for call in getattr(msg, "tool_calls", []) or []:
                if isinstance(call, dict) and call.get("name"):
                    tool_calls.append(str(call["name"]))

    if not reply:
        reply = "I connected to the research workspace, but I did not generate a final answer. Please try rephrasing the request."

    return JSONResponse(
        {
            "ok": True,
            "reply": reply,
            "toolCalls": sorted(set(tool_calls)),
            "model": llm_config["model"],
            "provider": llm_config["provider"],
            "context": context_summary,
        }
    )


@orchestrator.custom_route("/api/onboarding-chat", methods=["POST"])
async def onboarding_chat_api(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    raw_messages = body.get("messages") or []
    location_id = str(body.get("location_id") or "").strip()
    location_name = str(body.get("location_name") or "").strip() or "this location"
    user_name = str(body.get("user_name") or "").strip() or "there"
    provided_mcp_url = str(body.get("mcp_url") or "").strip()

    if not provided_mcp_url:
        return JSONResponse(
            {"ok": False, "error": "missing_mcp_url", "message": "Request JSON must include mcp_url."},
            status_code=400,
        )

    try:
        llm_config = _marketplace_llm_config()
    except ValueError as exc:
        return JSONResponse(
            {
                "ok": False,
                "error": "missing_llm_api_key",
                "message": str(exc),
                "provider": _marketplace_llm_provider(),
            },
            status_code=503,
        )

    try:
        messages = _coerce_marketplace_chat_messages(raw_messages)
    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "error": "invalid_request", "message": str(exc)},
            status_code=400,
        )

    try:
        from langchain_openai import ChatOpenAI
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langgraph.prebuilt import create_react_agent
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "llm_dependencies_unavailable", "message": str(exc)},
            status_code=500,
        )

    normalized_mcp_url = provided_mcp_url.rstrip("/")
    mcp_url = normalized_mcp_url if normalized_mcp_url.endswith("/mcp") else f"{normalized_mcp_url}/mcp"

    system_prompt = f"""
You are the LeadsMCP onboarding assistant embedded inside a GoHighLevel custom page.

Goals:
- Help the user onboard after installation.
- Speak in the context of their exact HighLevel location/sub-account.
- Explain how to connect AI clients like Claude Desktop, Cursor, or ChatGPT-compatible tooling.
- Recommend the fastest path to value using LeadsMCP tools.
- Troubleshoot setup and activation issues clearly.

Rules:
- You are connected to the user's LeadsMCP MCP server.
- Prefer practical next steps and concise guidance.
- If the user asks you to perform an action and a tool exists, use it.
- If you change or create records, briefly summarize what you changed.
- Keep responses formatted in clear markdown.

Session context:
- location_id: {location_id or 'unknown'}
- location_name: {location_name}
- current_user: {user_name}
- mcp_server_url: {normalized_mcp_url}
""".strip()

    try:
        client = MultiServerMCPClient(
            {
                "leadsmcp": {
                    "url": mcp_url,
                    "transport": "streamable_http",
                    "headers": {"X-GHL-Location-ID": location_id} if location_id else {},
                }
            }
        )
        tools = await client.get_tools()
        onboarding_tools = [
            tool for tool in tools
            if getattr(tool, "name", "").startswith("outscraper_")
            or getattr(tool, "name", "").startswith("ghl_")
        ]

        llm_kwargs: dict[str, Any] = {
            "model": llm_config["model"],
            "api_key": llm_config["api_key"],
            "temperature": 1e-8,
        }
        if llm_config.get("base_url"):
            llm_kwargs["base_url"] = llm_config["base_url"]

        llm = ChatOpenAI(**llm_kwargs)
        agent = create_react_agent(llm, onboarding_tools, prompt=system_prompt)
        result = await agent.ainvoke({"messages": messages})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "llm_run_failed", "message": str(exc)},
            status_code=500,
        )

    reply = ""
    tool_calls: list[str] = []
    for msg in result.get("messages", []):
        msg_type = getattr(msg, "type", "")
        if msg_type == "ai":
            text = _message_content_text(getattr(msg, "content", ""))
            if text:
                reply = text
            for call in getattr(msg, "tool_calls", []) or []:
                if isinstance(call, dict) and call.get("name"):
                    tool_calls.append(str(call["name"]))

    if not reply:
        reply = "I connected to the onboarding workspace, but I did not generate a final answer. Please try rephrasing the request."

    return JSONResponse(
        {
            "ok": True,
            "reply": reply,
            "toolCalls": sorted(set(tool_calls)),
            "model": llm_config["model"],
            "provider": llm_config["provider"],
            "context": {
                "locationId": location_id,
                "locationName": location_name,
                "userName": user_name,
                "mcpUrl": normalized_mcp_url,
            },
        }
    )


@orchestrator.custom_route("/api/marketplace/lead-search", methods=["POST"])
async def marketplace_lead_search(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    encrypted_data = str(body.get("encryptedData") or "").strip()
    search_type = str(body.get("searchType") or "").strip()
    raw_params = body.get("params") or {}

    if not encrypted_data:
        return JSONResponse(
            {"ok": False, "error": "missing_encrypted_data", "message": "Request JSON must include encryptedData."},
            status_code=400,
        )
    if search_type not in MARKETPLACE_SEARCH_TYPES:
        return JSONResponse(
            {
                "ok": False,
                "error": "unsupported_search_type",
                "message": f"Unsupported searchType '{search_type}'.",
                "supported": sorted(MARKETPLACE_SEARCH_TYPES.keys()),
            },
            status_code=400,
        )

    try:
        user_context = _decrypt_marketplace_user_context(encrypted_data)
        params = _coerce_marketplace_search_params(search_type, raw_params)
    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "error": "invalid_request", "message": str(exc)},
            status_code=400,
        )
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "context_decrypt_failed", "message": str(exc)},
            status_code=400,
        )

    started = time.perf_counter()
    try:
        result = await MARKETPLACE_SEARCH_TYPES[search_type]["handler"](**params)
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        return JSONResponse(
            {
                "ok": False,
                "error": "outscraper_request_failed",
                "message": detail,
                "status_code": status_code,
            },
            status_code=502,
        )
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "search_execution_failed", "message": str(exc)},
            status_code=502,
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    leads = _extract_marketplace_leads(search_type, result)
    geo_leads = [lead for lead in leads if lead.get("hasCoordinates")]
    return JSONResponse(
        {
            "ok": True,
            "searchType": search_type,
            "searchLabel": MARKETPLACE_SEARCH_TYPES[search_type]["label"],
            "params": params,
            "elapsedMs": elapsed_ms,
            "context": _marketplace_user_context_summary(user_context),
            "leadCount": len(leads),
            "geoLeadCount": len(geo_leads),
            "mapCenter": _marketplace_map_center(leads),
            "leads": leads,
            "result": result,
        }
    )


# ── Health check ──────────────────────────────────────────────────────────────
@orchestrator.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({
        "status": "healthy",
        "services": ["outscraper", "ghl", "stripe"],
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
        "ghl_oauth_success_redirect_configured": bool(os.getenv("GHL_OAUTH_SUCCESS_REDIRECT_URL", "").strip()),
        "ghl_callback_token_response_enabled": _allow_callback_token_response(),
        "ghl_install_store_path": str(_install_store_path()),
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
