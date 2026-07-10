# LeadsMCP Installation Guide

This guide is for licensed customers receiving LeadsMCP through a private
GitHub repository.

## What You Need Before You Start

- GitHub access to the private LeadsMCP repository
- your own Outscraper API key
- your own GoHighLevel marketplace app credentials or PIT token
- your own deployment target:
  - Vercel, or
  - Docker-compatible host
- optional Stripe credentials if using metered export billing

## Step 1: Clone the Repository

```bash
git clone <private-repo-url>
cd leadsmcp
```

## Step 2: Create Your Environment File

```bash
cp .env.example .env
```

Fill in the values for:
- `OUTSCRAPER_API_KEY` (optional fallback — customers can instead send their key
  per request via the `x-api-key` header from their MCP client, which takes
  precedence)
- `MCP_SECRET`
- `GHL_*`
- `STRIPE_*` if enabled
- `LEADSMCP_INSTALLS_DATABASE_URL` for durable token storage

## Step 3: Choose a Deployment Path

### Option A: Vercel
Follow [docs/DEPLOY-VERCEL.md](/Users/chad/MCP%20Servers/leadsmcp/docs/DEPLOY-VERCEL.md)

### Option B: Docker
Follow [docs/DEPLOY-DOCKER.md](/Users/chad/MCP%20Servers/leadsmcp/docs/DEPLOY-DOCKER.md)

## Step 4: Verify the Server

After deployment, confirm:
- root page loads
- `/health` returns healthy
- `/mcp` responds to MCP client connection
- GHL install callback works
- token refresh storage is durable

## Step 5: Connect a Client

Use one of the supported MCP client formats from the README.

## Recommended First Test

1. Connect with `x-mcp-secret`
2. Pass your Outscraper key as `x-api-key` (or rely on the `OUTSCRAPER_API_KEY` env fallback)
3. Pass a valid `locationId`
4. Run a simple GHL read tool
5. Run a search tool
5. Run a single contact create/upsert test

## Support Boundary

Support and update rights depend on the customer's commercial agreement.
