# Customer Onboarding Checklist

Use this checklist before handing LeadsMCP to a customer.

## Commercial
- customer agreement signed
- support scope confirmed
- billing model confirmed
- GitHub username collected

## Access
- customer invited to private repo
- release/version assigned
- install docs shared

## Customer-Owned Credentials
- Outscraper API key (sent per request as the `x-api-key` MCP client header; the
  `OUTSCRAPER_API_KEY` env var is an optional single-tenant fallback and the
  header takes precedence)
- GHL app credentials or PIT token
- GHL redirect URLs confirmed
- Stripe credentials if export billing is enabled
- Postgres database ready

## Deployment
- Vercel or Docker target chosen
- env vars loaded
- custom domain confirmed if applicable
- health check passes

## Functional Verification
- MCP connection succeeds
- `x-api-key` header set (or `OUTSCRAPER_API_KEY` fallback configured)
- GHL tools list successfully
- search tools list successfully
- one search run succeeds (confirms the Outscraper key resolves)
- one CRM write succeeds in correct location
- token refresh storage verified

## Handover
- customer has edit/admin access where appropriate
- support contact shared
- release notes shared
- rollback path documented
