# LeadsMCP — Outscraper + GoHighLevel + Stripe Metering

A single cloud-hosted MCP server that combines:
- Outscraper for lead search/enrichment
- Stripe for customer identity + qualified lead export billing
- GoHighLevel for CRM push/export

## Commercial Distribution

LeadsMCP is intended to be distributed as a private commercial product.

- Source code access is governed by the proprietary [LICENSE](/Users/chad/MCP%20Servers/leadsmcp/LICENSE)
- Recommended GitHub sales and delivery model: [docs/COMMERCIAL-DISTRIBUTION.md](/Users/chad/MCP%20Servers/leadsmcp/docs/COMMERCIAL-DISTRIBUTION.md)
- Customer installation guide: [INSTALL.md](/Users/chad/MCP%20Servers/leadsmcp/INSTALL.md)
- Vercel deployment guide: [docs/DEPLOY-VERCEL.md](/Users/chad/MCP%20Servers/leadsmcp/docs/DEPLOY-VERCEL.md)
- Docker deployment guide: [docs/DEPLOY-DOCKER.md](/Users/chad/MCP%20Servers/leadsmcp/docs/DEPLOY-DOCKER.md)
- Customer onboarding checklist: [docs/CUSTOMER-CHECKLIST.md](/Users/chad/MCP%20Servers/leadsmcp/docs/CUSTOMER-CHECKLIST.md)
- Release checklist: [docs/RELEASE-CHECKLIST.md](/Users/chad/MCP%20Servers/leadsmcp/docs/RELEASE-CHECKLIST.md)
- Public GitHub repo starter: [distribution/public-repo-starter/README.md](/Users/chad/MCP%20Servers/leadsmcp/distribution/public-repo-starter/README.md)
- Public repo creation guide: [distribution/CREATE-PUBLIC-REPO.md](/Users/chad/MCP%20Servers/leadsmcp/distribution/CREATE-PUBLIC-REPO.md)
- Checkout and access flow: [docs/onboarding/CHECKOUT-AND-ACCESS-FLOW.md](/Users/chad/MCP%20Servers/leadsmcp/docs/onboarding/CHECKOUT-AND-ACCESS-FLOW.md)
- Release package starter: [releases/v1.0.0/RELEASE-NOTES.md](/Users/chad/MCP%20Servers/leadsmcp/releases/v1.0.0/RELEASE-NOTES.md)
- Customer delivery checklist: [releases/v1.0.0/CUSTOMER-DELIVERY-CHECKLIST.md](/Users/chad/MCP%20Servers/leadsmcp/releases/v1.0.0/CUSTOMER-DELIVERY-CHECKLIST.md)

Recommended commercial model:

1. Bill customers outside GitHub using Stripe, GHL, or invoice.
2. Deliver the product through a private GitHub repo and tagged GitHub Releases.
3. Keep each customer on their own Outscraper account and deployment credentials.

## Project Structure

```
leadsmcp/
├── main.py                    ← Orchestrator (deploy this)
├── agent.py                   ← AI agent that uses the server
├── .env.example               ← Environment template (copy to .env)
├── servers/
│   ├── __init__.py
│   ├── outscraper_server.py   ← Outscraper tools
│   └── stripe_server.py       ← Stripe customer + quality analyzer + usage meter tools
├── scripts/
│   └── smoke_test.py          ← Startup + MCP connectivity smoke test
├── .env                       ← Your credentials (NEVER commit this)
├── requirements.txt
├── vercel.json                ← Vercel routing/runtime config
├── Dockerfile
├── railway.toml               ← Railway deployment config
└── render.yaml                ← Render deployment config
```

## Quick Start (Local)

```bash
# 1. Create your local env file from template
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the MCP server
python main.py
# Server runs at: http://localhost:8000
# MCP endpoint:   http://localhost:8000/mcp
# Health check:   http://localhost:8000/health

# 4. Run smoke test (health + list_tools + stripe dry-run)
python scripts/smoke_test.py --base-url http://localhost:8000

# 5. In a new terminal, run the agent (requires GEMINI_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY in .env)
python agent.py 1    # Task 1: Plumbers in Johannesburg → GHL
python agent.py 2    # Task 2: Marketing agencies in Cape Town → GHL + Pipeline
python agent.py 3    # Task 3: Restaurants in Sandton (read-only, safe test)
```

## Deploy to Railway (Recommended — free tier available)

```bash
npm install -g @railway/cli
railway login
railway init
railway up

# Set environment variables in Railway dashboard or CLI:
railway variables set OUTSCRAPER_API_KEY=your_outscraper_key_here
railway variables set MCP_SECRET=replace_with_long_random_secret
railway variables set CORS_ALLOWED_ORIGINS=https://your-app.example.com

# Optional default GHL fallback (single-tenant mode)
railway variables set GHL_PIT_TOKEN=pit-xxxx
railway variables set GHL_LOCATION_ID=xxxx
railway variables set GHL_API_VERSION=2021-07-28

# GHL Marketplace OAuth (required for multi-agency installs)
railway variables set GHL_CLIENT_ID=your_client_id
railway variables set GHL_CLIENT_SECRET=your_client_secret
railway variables set GHL_OAUTH_REDIRECT_URI=https://your-domain.com/oauth/ghl/callback
railway variables set GHL_OAUTH_INSTALL_URL='your_ghl_install_url'
railway variables set GHL_OAUTH_SCOPES='contacts.readonly contacts.write conversations.readonly conversations.write conversations/message.readonly conversations/message.write opportunities.readonly opportunities.write calendars.readonly calendars.write calendars/events.readonly calendars/events.write payments/orders.readonly payments/transactions.readonly locations/customFields.readonly forms.readonly locations.readonly socialplanner/post.readonly socialplanner/post.write socialplanner/statistics.readonly socialplanner/account.readonly emails/builder.write emails/builder.readonly blogs/list.readonly blogs/posts.readonly blogs/author.readonly blogs/category.readonly blogs/post-update.write blogs/check-slug.readonly blogs/post.write'
railway variables set GHL_OAUTH_TOKEN_URL=https://services.leadconnectorhq.com/oauth/token
railway variables set GHL_OAUTH_USER_TYPE=Location
railway variables set GHL_OAUTH_REQUIRE_STATE=true
railway variables set GHL_OAUTH_STATE_TTL_SECONDS=900
railway variables set GHL_OAUTH_STATE_SECRET=replace_with_long_random_secret
railway variables set GHL_OAUTH_SUCCESS_REDIRECT_URL=https://your-app.com/integrations/ghl/connected
railway variables set GHL_OAUTH_ALLOW_TOKEN_RESPONSE_IN_PRODUCTION=false
railway variables set LEADSMCP_INSTALLS_DATABASE_URL=postgresql://user:pass@host/db
# Optional local fallback only when no database URL is configured
railway variables set GHL_INSTALL_STORE_PATH=/tmp/leadsmcp_ghl_installs.jsonl
railway variables set GHL_INSTALL_ENCRYPTION_SECRET=replace_with_long_random_secret
railway variables set GHL_AUTO_REFRESH_MANAGED_TOKENS=true
railway variables set GHL_AUTO_TOKEN_PRIORITY=managed
railway variables set GHL_AUTO_REFRESH_SKEW_SECONDS=300

railway variables set GEMINI_API_KEY=AIza_your_gemini_key_here
railway variables set LEADSMCP_MARKETPLACE_LLM_PROVIDER=google

# Stripe usage billing vars
railway variables set STRIPE_SECRET_KEY=sk_test_or_live_xxx
railway variables set STRIPE_API_VERSION=2026-02-25.clover
railway variables set STRIPE_METER_EVENT_NAME=qualified_lead_export
railway variables set STRIPE_METER_VALUE_FIELD=leads_exported
railway variables set STRIPE_METER_CUSTOMER_FIELD=stripe_customer_id
railway variables set STRIPE_METERED_PRICE_ID=price_xxx
railway variables set QUALIFIED_LEAD_UNIT_PRICE_USD=1.20
railway variables set BILLING_CONSENT_MODE=per_batch
railway variables set BILLING_REQUIRE_EXPORT_BATCH_ID=true
railway variables set STRIPE_ENFORCE_EXPORT_ACCESS_CHECK=true
railway variables set QUALIFIED_LEAD_VERIFIED_EMAIL_STATUSES=valid,verified,receiving
railway variables set QUALIFIED_LEAD_VERIFIED_PHONE_STATUSES=valid,verified,mobile,landline
```

Your MCP endpoint will be: `https://your-app.railway.app/mcp`

## Deploy to Render

Push to GitHub, connect Render to the repo, and it auto-reads `render.yaml`.
Add env vars in the Render dashboard.

## Deploy with Docker

```bash
docker build -t mcp-orchestrator .
docker run -p 8000:8000 --env-file .env mcp-orchestrator
```

## Connect MCP Clients

### Claude Desktop / Cursor / Windsurf
Add to your MCP config:
```json
{
  "mcpServers": {
    "my-orchestrator": {
      "url": "https://your-app.example.com/mcp",
      "transport": "streamable_http",
      "headers": {
        "x-mcp-secret": "your_mcp_secret",
        "x-api-key": "your_outscraper_api_key",
        "x-ghl-token": "pit_or_oauth_access_token",
        "x-ghl-location-id": "location_or_subaccount_id",
        "x-ghl-version": "2021-07-28"
      }
    }
  }
}
```

Official GHL MCP header format is also supported directly:
```json
{
  "mcpServers": {
    "leadsmcp": {
      "url": "https://your-app.example.com/mcp",
      "headers": {
        "x-mcp-secret": "your_mcp_secret",
        "x-api-key": "your_outscraper_api_key",
        "Authorization": "Bearer <ghl_token>",
        "locationId": "<subaccount_id>",
        "version": "2021-07-28"
      }
    }
  }
}
```

### n8n (v1.104+)
Use the MCP node with transport: Streamable HTTP
URL: https://your-app.railway.app/mcp

## Multi-Agency GHL Tenancy

The server now supports multi-tenant GHL routing per request:

- `x-ghl-token`: agency/subaccount token for that tenant
- `x-ghl-location-id`: target location/subaccount id
- `x-ghl-version` (optional): defaults to `2021-07-28`
- `x-tenant-id` (optional): explicit tenant key used to resolve managed install records
- `Authorization` + `locationId` + `version`: official GHL MCP header shape (also accepted)
- `x-mcp-secret`: required server auth header when `MCP_SECRET` is set
- `x-api-key`: per-request Outscraper API key used by all `outscraper_*` tools

Behavior:

1. If tenant headers are present, `ghl_*` tools use that tenant context.
2. If `GHL_AUTO_REFRESH_MANAGED_TOKENS=true`, leadsmcp can resolve tenant credentials from install records and auto-refresh expired access tokens using the stored encrypted refresh token.
3. If no tenant context resolves, server falls back to `GHL_PIT_TOKEN` + `GHL_LOCATION_ID`.
4. `outscraper_*` tools resolve the Outscraper key per request (see below). Stripe remains a shared platform integration from server env vars.

### Per-Customer Outscraper Credentials

`outscraper_*` tools resolve the Outscraper API key **per request** so each
customer can bill their own Outscraper account:

- Send your Outscraper key as the `x-api-key` header from your MCP client.
- The header takes precedence over any server-side value.
- If `x-api-key` is absent, the server falls back to the `OUTSCRAPER_API_KEY`
  environment variable (single-tenant / compatibility mode).
- If neither is present, Outscraper tools return a clear error asking for the
  key — the key value is never logged or persisted.

This means other agencies can connect to the same LeadsMCP deployment safely using their own GHL credentials without sharing your default account.

### GHL Tool Allowlist

The GoHighLevel native MCP exposes a large tool surface (contacts, opportunities,
conversations, calendars, payments, locations, forms, social planner, email builder,
blogs). LeadsMCP proxies that endpoint, so without filtering every one of those tools
is re-exported as `ghl_<group>_<action>` — far more than the lead/contact workflow
needs. A middleware prunes the proxied `ghl_*` tools to a configurable allowlist:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GHL_ENABLED_TOOL_GROUPS` | `contacts,opportunities,conversations,locations` | GHL tool groups to expose (matched against the `<group>` segment). |
| `GHL_ENABLED_TOOLS` | _(empty)_ | Extra individual tools to re-enable from otherwise-disabled groups. `ghl_` prefix optional; hyphens or underscores accepted. |
| `GHL_TOOL_ALLOWLIST_DISABLED` | `false` | Set `true` to expose the full GHL surface (no filtering) for debugging. |

`ghl_contacts_create-contact` and `ghl_contacts_upsert-contact` are always enabled so
CRM writes cannot be filtered out by a mis-configured group list. Use the hyphenated
canonical names when calling; common aliases such as `ghl_create_contact` are
automatically rewritten to `ghl_contacts_create-contact`.

> **create-contact not active?** It requires a GHL token with the `contacts.write`
> scope. Confirm the scope is granted (see `GHL_OAUTH_SCOPES`) and that a tenant token
> or `GHL_PIT_TOKEN` is present; the tool is otherwise not returned by the GHL endpoint.

### Durable Install Storage

For production multi-tenant installs, set `LEADSMCP_INSTALLS_DATABASE_URL` to a Postgres connection string.
The server also auto-detects provider-prefixed env vars such as `leadsmcpstorage_POSTGRES_URL` from the Vercel Supabase integration.

- When set, install records and encrypted refresh tokens are stored in Postgres.
- When not set, leadsmcp falls back to `GHL_INSTALL_STORE_PATH` JSONL storage.
- JSONL fallback is acceptable for local testing, but it is not durable on Vercel serverless instances.
- Check `/health` and confirm:
  - `ghl_install_store_backend=postgres`
  - `ghl_install_store_database_env_key=<your postgres env var>`
  - `ghl_install_store_database_url_configured=true`
  - `ghl_install_store_driver_available=true`

### Scheduled Token Refresh

Leadsmcp can proactively refresh managed GHL install tokens on a daily schedule.

- Vercel Cron path: `GET /api/cron/ghl-refresh-installs`
- Manual admin trigger: `POST /admin/ghl/refresh-expiring-installs`
- Auth:
  - Vercel Cron uses `Authorization: Bearer <CRON_SECRET>`
  - Manual admin calls can continue using `x-mcp-secret`

Recommended env:

- `GHL_SCHEDULED_REFRESH_ENABLED=true`
- `GHL_SCHEDULED_REFRESH_LOOKAHEAD_SECONDS=86400`
- `GHL_SCHEDULED_REFRESH_BATCH_LIMIT=100`
- `CRON_SECRET=<long random secret>`

Refresh behavior:

1. Load the latest install record per tenant/location.
2. Refresh any record expiring within the lookahead window.
3. Persist the new access token and rotated refresh token back to Postgres.
4. Continue to use on-demand refresh during live MCP calls as the primary safety net.

## GoHighLevel Marketplace Fit

For a GHL Marketplace app install flow, your app backend should:

1. Start the OAuth flow via `GET /oauth/ghl/start` (or use your marketplace installation URL directly).
2. Handle callback at `GET /oauth/ghl/callback` on this server.
3. Use `POST /oauth/ghl/exchange` if you want server-to-server exchange instead of browser callback exchange.
4. Use `POST /oauth/ghl/refresh` to rotate expired access tokens.
5. Use `POST /admin/ghl/refresh-by-location` to force-refresh a stored tenant token by `location_id`, `tenant_id`, or `company_id` without handling raw refresh tokens manually.
6. On each MCP call, inject `x-ghl-token` and `x-ghl-location-id` from that install context, or send only tenant context and let the server resolve managed credentials.
7. Always include `x-mcp-secret` when calling your hosted MCP endpoint.

If auto-managed refresh is enabled, you can also send only tenant context (`locationId` / `x-ghl-location-id`, optionally `x-tenant-id`) and let leadsmcp resolve + refresh access tokens server-side.

This repo is now compatible with that model because GHL credentials are request-scoped, not hardcoded to one location.

### OAuth Endpoints (now built-in)

- `GET /oauth/ghl/start`:
  - Creates signed state and redirects to `GHL_OAUTH_INSTALL_URL`.
  - Always injects the configured `GHL_OAUTH_SCOPES` (or built-in MCP default scope set) into the install URL.
  - If `GHL_OAUTH_INSTALL_URL` is blank, auto-builds a `marketplace.gohighlevel.com/oauth/chooselocation` URL from `GHL_CLIENT_ID` + `GHL_OAUTH_REDIRECT_URI`.
  - Accepts optional query params: `tenant_id`, `customer_id`, `return_to`, `user_type`.
- `GET /oauth/ghl/callback`:
  - Accepts `code` from HighLevel and exchanges it for tokens.
  - Verifies signed state when provided (or requires it if `GHL_OAUTH_REQUIRE_STATE=true`).
  - Persists install metadata server-side and stores `refresh_token` encrypted at rest.
  - If `GHL_OAUTH_SUCCESS_REDIRECT_URL` is set, browser callback redirects with status params (no raw tokens).
- `GET /leadsmcp/install`:
  - Alias of `/oauth/ghl/callback` for marketplace setups already using this redirect path.
- `GET /leadsmcp-install/`:
  - Alias of `/oauth/ghl/callback` for marketplace setups using the hyphenated redirect path.
- `POST /oauth/ghl/exchange` (protected by `x-mcp-secret`):
  - JSON body: `{ "code": "...", "user_type": "Location", "redirect_uri": "..." }`
- `POST /oauth/ghl/refresh` (protected by `x-mcp-secret`):
  - JSON body: `{ "refresh_token": "...", "user_type": "Location", "redirect_uri": "..." }`
- `POST /admin/ghl/refresh-by-location` (protected by `x-mcp-secret`):
  - JSON body: `{ "location_id": "...", "tenant_id": "...", "company_id": "..." }`
  - Requires at least one selector.
  - Uses the stored encrypted refresh token and returns safe metadata only (`tokens_hidden=true`).
- `POST /admin/ghl/refresh-expiring-installs` (protected by `x-mcp-secret`):
  - JSON body: `{ "lookahead_seconds": 86400, "batch_limit": 100 }`
  - Refreshes due managed installs in bulk and returns a summary.
- `GET /api/cron/ghl-refresh-installs`:
  - Daily Vercel Cron target.
  - Uses `Authorization: Bearer <CRON_SECRET>`.

### GHL Custom Marketplace Page

Leadsmcp now includes a custom-page-ready search workspace for HighLevel Marketplace apps:

- Page URL: `GET /app/lead-search`
- Context endpoint: `POST /api/marketplace/user-context`
- Search endpoint: `POST /api/marketplace/lead-search`

What it does:

1. Loads inside a HighLevel custom page iframe.
2. Requests encrypted user context from the parent window using `REQUEST_USER_DATA`.
3. Decrypts that payload server-side with `GHL_APP_SHARED_SECRET`.
4. Shows the connected company/location/user context inside the page.
5. Lets the user choose a supported search mode and fill the required parameters.
6. Runs the search server-side against the existing Outscraper integration and returns the raw payload.

Current supported search types:

- `google_maps_search`
- `emails_and_contacts`
- `google_search`

Required env:

- `GHL_APP_SHARED_SECRET=<your marketplace app shared secret>`

Without that secret, the custom page can render but it cannot decrypt user context from HighLevel.

### Use with deployed agent
```bash
MCP_SERVER_URL=https://your-app.railway.app/mcp python agent.py 1
```

## Stripe Usage-Based Billing Flow

Use this flow for PAYG CRM export:

1. User searches leads (results are free to browse).
2. Before exposing full export path, collect:
   - full name
   - first name
   - last name
   - email
   - phone
3. Call `stripe_ensure_customer_profile` to create/update Stripe customer.
4. Analyze quality + quote via `stripe_analyze_qualified_lead_export`:
   - Applies qualification rule:
     `full_name AND job_title AND (verified_email OR verified_phone)`
   - Returns a per-company breakdown and total qualified leads.
5. Create an `export_batch_id` and call `stripe_plan_qualified_lead_export_billing`.
6. If `checkout_required=true`, send `checkout.checkout_url` (or call `stripe_create_usage_checkout_session` manually).
7. If `permission_required=true`, request explicit user approval for this exact batch and cost.
8. Once approved, call `stripe_record_qualified_lead_export` with:
   - `export_batch_id`
   - `tenant_id` (if multi-tenant)
   - `consent_granted=true`
   - `tier_a_leads` / `tier_b_leads` or `leads_exported`
9. Only then push contacts/opportunities into `ghl_*` tools.

### Double-charge safeguards

`stripe_record_qualified_lead_export` includes multiple protections:
- Export batch guard: with `BILLING_REQUIRE_EXPORT_BATCH_ID=true`, each export must have a batch id.
- In-memory + JSONL ledger guard: repeated calls for the same `(tenant_id, stripe_customer_id, export_batch_id)` return already-recorded status.
- Stripe idempotency key: deterministic key per batch is sent to Stripe meter events.
- Access gate: with `STRIPE_ENFORCE_EXPORT_ACCESS_CHECK=true`, meter writes are blocked unless subscription access is active.
- Consent gate: with `BILLING_CONSENT_MODE=per_batch`, writes are blocked unless `consent_granted=true`.

Meter event defaults:
- `event_name`: `qualified_lead_export`
- `payload[stripe_customer_id]`: Stripe customer id
- `payload[leads_exported]`: number of qualified leads exported
- `payload[export_batch_id]`: export batch identifier
- `payload[tenant_id]`: tenant key when supplied

## Adding More Services

To add a new service (e.g. Twilio, HubSpot):

1. Create `servers/my_service_server.py` with a `FastMCP` instance + tools
2. In `main.py`, add:
   ```python
   from servers.my_service_server import mcp as my_service_mcp
   orchestrator.mount(my_service_mcp, prefix="myservice")
   ```
3. Redeploy — the new tools appear immediately

## Available Tools

Actual callable name is `prefix + tool` (example: `outscraper_google_maps_search`).

| Tool | Prefix | Description |
|------|--------|-------------|
| google_maps_search | outscraper_ | Find businesses on Google Maps |
| google_maps_reviews | outscraper_ | Fetch business reviews |
| google_search | outscraper_ | Research prospects |
| google_search_news | outscraper_ | Search Google News |
| google_trends | outscraper_ | Pull trend signals for search terms |
| emails_and_contacts | outscraper_ | Website scraper for domain contacts (serial, one domain per request) |
| email_validator | outscraper_ | Check email deliverability |
| phones_enricher | outscraper_ | Validate phones + carrier data |
| similarweb | outscraper_ | Website traffic and ranking insights |
| profile_balance | outscraper_ | Outscraper account credits/usage |
| get_request_results | outscraper_ | Poll async Outscraper jobs |
| dynamic proxied tools | ghl_ | Auto-proxied from GHL MCP (names vary by account/modules) |
| ensure_customer_profile | stripe_ | Create/update Stripe customer from user details |
| analyze_qualified_lead_export | stripe_ | Count qualified leads, per-company breakdown, and quote |
| plan_qualified_lead_export_billing | stripe_ | Decide checkout vs explicit permission vs ready-to-export |
| estimate_qualified_lead_export_cost | stripe_ | Quote helper (flat by qualified leads or legacy graduated mode) |
| get_customer_export_access | stripe_ | Check if customer is allowed to export |
| create_usage_checkout_session | stripe_ | Start Stripe subscription checkout |
| record_qualified_lead_export | stripe_ | Fire metered usage event with batch/consent safeguards |

## GHL Tool Availability Checks

If `create-contact` is missing from tool discovery, verify these first:
- `Authorization: Bearer <token>` is present.
- `locationId: <subaccount_id>` is present.
- Token has `contacts.write` scope.

Expected tool names when write scope is active:
- `ghl_contacts_create-contact`
- `ghl_contacts_upsert-contact`

## Security Notes
- NEVER commit `.env` to Git — it's in `.gitignore`
- Rotate your GHL PIT token at Settings → Private Integrations if exposed
- Rotate Stripe secret keys immediately if exposed
- Keep `GHL_OAUTH_ALLOW_TOKEN_RESPONSE_IN_PRODUCTION=false` so browser callbacks don't expose raw OAuth tokens
- Set `GHL_INSTALL_ENCRYPTION_SECRET` to encrypt stored refresh tokens at rest
- `MCP_SECRET` is enforced via `x-mcp-secret` on non-public routes (`/mcp` included)
