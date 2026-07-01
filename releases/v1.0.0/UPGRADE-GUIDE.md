# Upgrade Guide for v1.0.0

## New Customer
Follow the full installation flow.

## Existing Customer
1. pull the tagged release
2. compare `.env.example` against your current env vars
3. verify database-backed install storage remains configured
4. redeploy
5. run post-deploy checks:
   - `/health`
   - `/mcp`
   - GHL tool listing
   - one safe search
