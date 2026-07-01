# Deploy LeadsMCP to Vercel

## Recommended When

Use Vercel when you want:
- fast hosted deployment
- custom domain support
- scheduled refresh via Vercel Cron
- tight fit with the current repo structure

## Steps

### 1. Import the private repo into Vercel
- Create a new Vercel project
- Connect the private GitHub repository

### 2. Configure environment variables
At minimum set:
- `OUTSCRAPER_API_KEY`
- `MCP_SECRET`
- `LEADSMCP_INSTALLS_DATABASE_URL`
- `GHL_INSTALL_ENCRYPTION_SECRET`
- `GHL_CLIENT_ID`
- `GHL_CLIENT_SECRET`
- `GHL_OAUTH_REDIRECT_URI`
- `GHL_OAUTH_SUCCESS_REDIRECT_URL`
- `GHL_OAUTH_INSTALL_URL`
- `GHL_APP_SHARED_SECRET` if using GHL custom pages
- `MAPBOX_PUBLIC_TOKEN` if using the map UI
- `CRON_SECRET`

Optional:
- `STRIPE_SECRET_KEY`
- `STRIPE_METERED_PRICE_ID`
- `OPENAI_API_KEY`

### 3. Deploy
Vercel will use the repo configuration already included in `vercel.json`.

### 4. Verify routes
Check:
- `/`
- `/health`
- `/mcp`
- `/leadsmcp-install/`
- `/app-install-successfully/`
- `/app/lead-search/`

### 5. Verify durable install storage
`/health` should show:
- `ghl_install_store_backend=postgres`
- database configured true

## Production Recommendation

Use a custom domain and update GHL redirect URLs to match that domain exactly.
