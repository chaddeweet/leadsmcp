# Customer Delivery Checklist for v1.0.0

Use this for the first real customer handoff.

## Before Sending Access
- confirm payment or signed agreement
- confirm plan type
- confirm support scope
- collect customer GitHub username or email
- confirm whether setup is self-hosted or managed

## Access Package
- invite customer to private GitHub repo
- assign supported release tag
- send `INSTALL.md`
- send deployment guide for chosen path
- send onboarding checklist
- send release notes

## Customer-Owned Inputs to Confirm
- Outscraper API key
- GoHighLevel app credentials or PIT token
- GoHighLevel redirect URLs
- Postgres database connection string
- Stripe credentials if export billing is enabled
- target deployment path: Vercel or Docker

## First Live Validation
- repo access confirmed
- deployment created
- `/health` returns healthy
- `/mcp` is reachable
- one search run succeeds
- one GHL read succeeds
- one GHL write succeeds in the correct location
- install storage backend is durable
- token refresh path is verified

## Handover Complete When
- customer has working deployment
- customer can connect their MCP client
- customer can run search and CRM sync successfully
- customer knows where to request support
