# MCP Integration Guide

LeadsMCP exposes a remote MCP endpoint that can be connected to compatible clients.

Typical connection shape:

```json
{
  "mcpServers": {
    "leadsmcp": {
      "url": "https://your-domain.example.com/mcp",
      "headers": {
        "x-mcp-secret": "your_mcp_secret",
        "x-api-key": "your_outscraper_api_key",
        "Authorization": "Bearer <ghl_token>",
        "locationId": "<ghl_location_id>",
        "version": "2021-07-28"
      }
    }
  }
}
```

## Outscraper API Key (`x-api-key`)

The `outscraper_*` tools resolve your Outscraper API key **per request** so each
customer bills their own Outscraper account:

- Send your Outscraper key as the `x-api-key` header (shown above).
- The header always takes precedence over any server-side value.
- If `x-api-key` is omitted, the server falls back to the `OUTSCRAPER_API_KEY`
  environment variable when configured (single-tenant mode).
- If neither is present, Outscraper tools return a clear error. The key value is
  never logged or persisted.

LeadsMCP can also resolve managed GHL credentials server-side when the install and token storage path is configured correctly.
