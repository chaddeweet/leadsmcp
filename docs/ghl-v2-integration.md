# GoHighLevel / LeadConnector MCP v2

LeadsMCP proxies HighLevel's official v2 MCP endpoint through the existing
tenant-aware FastMCP transport.

## Architecture

The default upstream endpoint is:

`https://services.leadconnectorhq.com/mcp/anthropic/v2`

HighLevel v2 exposes a compact catalog of five tools:

- `ghl_search`
- `ghl_fetch`
- `ghl_search_operations`
- `ghl_describe_operation`
- `ghl_execute_operation`

`ghl_search_operations` discovers the operations available to the connected
location. `ghl_describe_operation` returns the current input schema, and
`ghl_execute_operation` performs the selected operation. This gives LeadsMCP
access to the full upstream catalog without maintaining hundreds of hard-coded
endpoint schemas.

## Authentication and location scoping

The existing `GHLTenantAwareTransport` remains in use. Credentials are resolved
in this order:

1. Per-request `x-ghl-token` and `x-ghl-location-id` headers.
2. Standard `Authorization` and `locationId` headers.
3. Server defaults from `GHL_PIT_TOKEN` and `GHL_LOCATION_ID`.

Each connection remains scoped to one HighLevel sub-account. The operation
catalog is limited to the scopes granted to that location's OAuth token or PIT.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GHL_MCP_URL` | `https://services.leadconnectorhq.com/mcp/anthropic/v2` | Override the upstream v2 MCP endpoint. |
| `GHL_PIT_TOKEN` | empty | Optional fallback PIT when request credentials are absent. |
| `GHL_LOCATION_ID` | empty | Optional fallback location ID. |
| `GHL_V2_TOOL_ALLOWLIST_ENABLED` | `false` | Enable the legacy lead/contact tool allowlist. |
| `GHL_ENABLED_TOOL_GROUPS` | `contacts,opportunities,conversations,locations` | Groups used in legacy compatibility mode. |
| `GHL_ENABLED_TOOLS` | empty | Additional tools used in compatibility mode. |
| `GHL_TOOL_ALLOWLIST_DISABLED` | `false` | Bypass filtering after compatibility mode is enabled. |

## Using the catalog

1. Call `ghl_search_operations` with the user's intent.
2. Select the appropriate operation returned by HighLevel.
3. Call `ghl_describe_operation` to obtain its current schema.
4. Validate and collect the required arguments.
5. Obtain explicit user confirmation for destructive, financial, messaging, or
   otherwise irreversible operations.
6. Call `ghl_execute_operation`.

## Compatibility

The previous allowlist middleware remains available for deployments that only
want lead and contact workflows. Set `GHL_V2_TOOL_ALLOWLIST_ENABLED=true` to
enable it. New deployments expose the complete v2 catalog by default.

## Limitations

- Coverage depends on the scopes granted to the current location connection.
- Operation discovery is live; LeadsMCP does not bundle a stale offline catalog.
- HighLevel may add or change operations without a LeadsMCP code release.
- A live smoke test with a real location token is recommended before production
  deployment.
