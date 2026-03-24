# MCP Orchestrator — Outscraper + GoHighLevel

A single cloud-hosted MCP server that connects Outscraper and GoHighLevel into one endpoint.

## Project Structure

```
mcp-orchestrator/
├── main.py                    ← Orchestrator (deploy this)
├── agent.py                   ← AI agent that uses the server
├── servers/
│   ├── __init__.py
│   └── outscraper_server.py   ← Outscraper tools
├── .env                       ← Your credentials (NEVER commit this)
├── requirements.txt
├── Dockerfile
├── railway.toml               ← Railway deployment config
└── render.yaml                ← Render deployment config
```

## Quick Start (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the MCP server
python main.py
# Server runs at: http://localhost:8000
# MCP endpoint:   http://localhost:8000/mcp
# Health check:   http://localhost:8000/health

# 3. In a new terminal, run the agent (requires OPENAI_API_KEY in .env)
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
railway variables set OUTSCRAPER_API_KEY=MmNlNzY3NTk2ZjNkNGZlMWExYmVjZDkxNGNjNjI0ZGF8NjIwMzk3Zjk0Nw
railway variables set GHL_PIT_TOKEN=pit-013b8c62-824d-4880-9da4-5b248bd67509
railway variables set GHL_LOCATION_ID=5fMBh61yvJqYSuLpGMvV
railway variables set OPENAI_API_KEY=sk-your-key-here
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
      "url": "https://your-app.railway.app/mcp",
      "transport": "streamable_http"
    }
  }
}
```

### n8n (v1.104+)
Use the MCP node with transport: Streamable HTTP
URL: https://your-app.railway.app/mcp

### Use with deployed agent
```bash
MCP_SERVER_URL=https://your-app.railway.app/mcp python agent.py 1
```

## Adding More Services

To add a new service (e.g. Twilio, Stripe, HubSpot):

1. Create `servers/my_service_server.py` with a `FastMCP` instance + tools
2. In `main.py`, add:
   ```python
   from servers.my_service_server import mcp as my_service_mcp
   orchestrator.mount(my_service_mcp, prefix="myservice")
   ```
3. Redeploy — the new tools appear immediately

## Available Tools

| Tool | Prefix | Description |
|------|--------|-------------|
| search_google_maps | outscraper_ | Find businesses on Google Maps |
| search_business_records | outscraper_ | Query pre-built business DB |
| get_google_maps_reviews | outscraper_ | Fetch business reviews |
| validate_emails | outscraper_ | Check email deliverability |
| enrich_phone_numbers | outscraper_ | Validate phones + carrier data |
| get_company_insights | outscraper_ | Firmographics by domain |
| find_company_website | outscraper_ | Find company URL by name |
| google_search | outscraper_ | Research prospects |
| get_request_results | outscraper_ | Poll async requests |
| contacts_upsert-contact | ghl_ | Create/update GHL contact |
| contacts_add-tags | ghl_ | Tag a GHL contact |
| contacts_get-contacts | ghl_ | Search GHL contacts |
| opportunities_get-pipelines | ghl_ | List GHL pipelines |
| opportunities_create-opportunity | ghl_ | Add to pipeline |
| conversations_send-a-new-message | ghl_ | Send SMS/email via GHL |
| + 20 more GHL tools | ghl_ | Auto-proxied from GHL MCP |

## Security Notes
- NEVER commit `.env` to Git — it's in `.gitignore`
- Rotate your GHL PIT token at Settings → Private Integrations if exposed
- Add a `MCP_SECRET` bearer token auth layer before making the server public
