# Deployment Readiness — Stripe & Outscraper MCP

Status snapshot for the Stripe + Outscraper MCP surface. Use this alongside
[DEPLOY-VERCEL.md](./DEPLOY-VERCEL.md) and [DEPLOY-DOCKER.md](./DEPLOY-DOCKER.md).

## What is ready

- **Outscraper auth** — every request injects `X-API-KEY` via
  `servers/outscraper_server.py::_resolve_api_key()`. Precedence: inbound
  `x-api-key` request header (per-tenant), then the `OUTSCRAPER_API_KEY` env
  var. A missing key raises a clear error and the key is never logged or placed
  in query params.
- **Outscraper defaults** — `async=false` and `ui=false` are *enforced* on
  every call (query and JSON), so results return synchronously and are never
  promoted to a UI task. Callers cannot override these.
- **Rate-limit / retry** — shared backoff in `servers/http_retry.py`:
  - Retries HTTP 429 and 5xx plus transient network errors.
  - Honours the upstream `Retry-After` header when present.
  - Capped exponential backoff with full jitter.
  - **Stripe safety:** writes are retried only when they carry an
    `Idempotency-Key` (metered usage events do); keyless POSTs are never
    retried, preventing double-charges.
- **Tool manifest** — `tools.json` documents all 28 tools (21 Outscraper, 7
  Stripe) with namespaced names, descriptions, and input/output JSON schemas.
  Regenerate/verify with `python scripts/generate_tools_manifest.py [--check]`.
  A test (`tests/test_tools_manifest.py`) fails if it drifts from the registry.
- **Tests** — `pytest tests/` covers auth header injection, default
  enforcement, retry/backoff, no-unsafe-retry, error mapping, a
  customer→access→usage chained workflow, and manifest consistency.

## Configuration template

Server env (see `.env.example` for the full list):

```
# Outscraper (shared fallback key; tenants may override per request via x-api-key)
OUTSCRAPER_API_KEY=your_outscraper_key_here

# Stripe billing
STRIPE_SECRET_KEY=sk_live_or_test_key_here
STRIPE_API_VERSION=2026-02-25.clover
STRIPE_METERED_PRICE_ID=price_XXXXXXXXXXXX

# MCP endpoint auth
MCP_SECRET=replace_with_a_long_random_secret
```

Per-request headers a client may send:

| Header | Purpose |
| --- | --- |
| `x-mcp-secret` | Required when `MCP_SECRET` is set. |
| `x-api-key` | Optional per-tenant Outscraper key (else server env is used). |
| `x-ghl-token` / `x-ghl-location-id` | GHL tenancy (see README). |

## Registering the hosted endpoint

Endpoint: `https://<your-domain>/mcp` (transport: Streamable HTTP).

### Claude Desktop / Cursor / Windsurf

```json
{
  "mcpServers": {
    "leadsmcp": {
      "url": "https://your-app.example.com/mcp",
      "transport": "streamable_http",
      "headers": {
        "x-mcp-secret": "your_mcp_secret",
        "x-api-key": "your_outscraper_key"
      }
    }
  }
}
```

### TypingMind

Add a custom MCP/remote server:
- **Server URL:** `https://your-app.example.com/mcp`
- **Transport:** Streamable HTTP
- **Custom headers:** `x-mcp-secret: <secret>`, and optionally
  `x-api-key: <outscraper key>` plus the GHL tenancy headers.

After connecting, the tools appear namespaced as `outscraper_*` and `stripe_*`
(matching `tools.json`).

## Remaining steps — require user confirmation

These were intentionally **not** performed (they change remote state or expose
secrets):

1. **Provision production secrets** in the host (Vercel/Docker/Railway):
   `OUTSCRAPER_API_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_METERED_PRICE_ID`,
   `MCP_SECRET`, and the GHL/OAuth values.  
   **Also required for connector OAuth:** `SUPABASE_URL` and
   `SUPABASE_SERVICE_ROLE_KEY` — without these, `connector_oauth.py` falls back
   to an in-process token store that does not survive Vercel cold-start invocations.

2. **Apply the Supabase migration** before first deploy:
   ```bash
   # Install Supabase CLI if not present: brew install supabase/tap/supabase
   supabase db push --db-url "$SUPABASE_DB_URL"
   # Or apply manually:
   psql "$SUPABASE_DB_URL" -f migrations/0001_connector_oauth.sql
   ```

3. **Deploy** to the HTTPS target and confirm `/health` and `/mcp` respond.

4. **Register** the endpoint in the target client (Claude Desktop / TypingMind)
   using the JSON above with the real domain and secret.

5. **Smoke-test** live: `outscraper_profile_balance`, then the
   customer→access→usage Stripe chain against test keys before going live.  
   Also verify `tempmail_create_inbox` returns a valid address to confirm
   `TEMPMAIL_RAPIDAPI_KEY` **and** `TEMPMAIL_AUTH_TOKEN` are both set (missing
   the second key returns HTTP 403 code 257).
