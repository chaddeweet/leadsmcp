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
        "Authorization": "Bearer <ghl_token>",
        "locationId": "<ghl_location_id>",
        "version": "2021-07-28"
      }
    }
  }
}
```

LeadsMCP can also resolve managed GHL credentials server-side when the install and token storage path is configured correctly.
