# LeadsMCP v1.0.0

## Summary

This release packages LeadsMCP for private commercial distribution with:
- live lead search and enrichment
- GoHighLevel MCP proxy and custom pages
- durable managed token storage
- scheduled token refresh support
- Stripe-qualified export billing support
- mobile-ready custom search workspace

## Highlights

### Core Server
- MCP endpoint for lead operations and CRM sync
- multi-tenant GHL routing support
- managed install storage with Postgres support
- proactive token refresh path

### UI and Customer Experience
- install success page
- marketplace custom search page
- map-based result review workspace
- mobile app packaging support

### Deployment
- Vercel-ready configuration
- Docker deployment path
- environment template included

## Recommended Customer Validation
- connect MCP client successfully
- verify GHL tools list
- run one search
- run one contact create or upsert in the correct subaccount
- confirm install storage backend is durable

## Breaking or Sensitive Notes
- customers should use their own Outscraper credentials
- customers should use their own GHL app installation and redirect configuration
- filesystem storage is not a supported production install store
