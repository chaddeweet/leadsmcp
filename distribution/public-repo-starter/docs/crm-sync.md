# CRM Sync Overview

LeadsMCP is designed to hand structured lead records into GoHighLevel.

Core behavior:
- search and enrich lead data
- preview before export
- apply billing guardrails if export billing is enabled
- create or upsert contacts in the correct GHL location
- apply tags and metadata after import

For multi-tenant use, the server should use durable install storage and managed token refresh.
