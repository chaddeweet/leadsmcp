# LeadsMCP Commercial Distribution Model

LeadsMCP is best distributed through GitHub as a private commercial repository,
not as a public open source project.

## Recommended Model

1. Payment happens outside GitHub.
   - Stripe checkout
   - GHL marketplace or funnel checkout
   - direct invoice / proposal

2. Delivery happens through GitHub.
   - private repository access for paying customers
   - versioned GitHub Releases
   - optional GHCR Docker image delivery

3. Customer-owned data accounts stay separate.
   - each customer should use their own Outscraper API account
   - each customer should use their own GHL marketplace app install and tokens
   - each customer should use their own Stripe configuration if metered billing
     is customer-specific

## Sales Packaging

Use one of these offers:

### 1. Private Server License
Customer gets:
- private GitHub repo access
- install documentation
- release updates during subscription term

Best for:
- technical operators
- agencies with their own deploy resources
- teams that want self-hosted control

### 2. Managed Setup Service
Customer gets:
- private GitHub repo access
- deployment help
- environment configuration
- GHL / Outscraper / Stripe onboarding

Best for:
- founders
- agencies
- teams that want faster go-live

### 3. White-Glove Enterprise Delivery
Customer gets:
- private repo or image delivery
- bespoke deployment target
- support SLA
- optional customization

Best for:
- multi-client agencies
- enterprise RevOps teams
- OEM / reseller opportunities

## GitHub Structure Recommendation

### Public GitHub presence
Use a public repo or public docs site for:
- landing page content
- screenshots and videos
- changelog summary
- install examples
- MCP client connection examples
- contact / pricing / demo links

Starter files for a public-facing repo live in:
- [distribution/public-repo-starter/README.md](/Users/chad/MCP%20Servers/leadsmcp/distribution/public-repo-starter/README.md)
- [distribution/public-repo-starter/docs/mcp-integration-guide.md](/Users/chad/MCP%20Servers/leadsmcp/distribution/public-repo-starter/docs/mcp-integration-guide.md)
- [distribution/public-repo-starter/docs/crm-sync.md](/Users/chad/MCP%20Servers/leadsmcp/distribution/public-repo-starter/docs/crm-sync.md)
- [distribution/public-repo-starter/docs/pricing.md](/Users/chad/MCP%20Servers/leadsmcp/distribution/public-repo-starter/docs/pricing.md)
- [distribution/public-repo-starter/docs/tagline-options.md](/Users/chad/MCP%20Servers/leadsmcp/distribution/public-repo-starter/docs/tagline-options.md)
- [distribution/CREATE-PUBLIC-REPO.md](/Users/chad/MCP%20Servers/leadsmcp/distribution/CREATE-PUBLIC-REPO.md)

### Private product repo
Use the private repo for:
- production server code
- deployment files
- customer installation docs
- release tags and release notes
- Docker artifacts

## Release Artifacts

Every customer-facing release should have:
- a semantic version tag such as `v1.2.0`
- release notes
- Docker image reference, if applicable
- environment variable checklist
- migration notes if config or schema changed

Starter release package files live in:
- [releases/v1.0.0/RELEASE-NOTES.md](/Users/chad/MCP%20Servers/leadsmcp/releases/v1.0.0/RELEASE-NOTES.md)
- [releases/v1.0.0/CUSTOMER-EMAIL.md](/Users/chad/MCP%20Servers/leadsmcp/releases/v1.0.0/CUSTOMER-EMAIL.md)
- [releases/v1.0.0/UPGRADE-GUIDE.md](/Users/chad/MCP%20Servers/leadsmcp/releases/v1.0.0/UPGRADE-GUIDE.md)
- [releases/v1.0.0/CUSTOMER-DELIVERY-CHECKLIST.md](/Users/chad/MCP%20Servers/leadsmcp/releases/v1.0.0/CUSTOMER-DELIVERY-CHECKLIST.md)

## Access Workflow

1. Customer pays or signs proposal.
2. Customer provides GitHub username or email.
3. Customer is invited to the private repo or customer team.
4. Customer receives onboarding links:
   - `INSTALL.md`
   - `docs/DEPLOY-VERCEL.md`
   - `docs/DEPLOY-DOCKER.md`
   - `docs/CUSTOMER-CHECKLIST.md`
5. Customer is assigned the current supported release.

The full checkout-to-access operational flow is documented in:
- [docs/onboarding/CHECKOUT-AND-ACCESS-FLOW.md](/Users/chad/MCP%20Servers/leadsmcp/docs/onboarding/CHECKOUT-AND-ACCESS-FLOW.md)
- [docs/onboarding/WEBHOOK-PAYLOAD-EXAMPLES.md](/Users/chad/MCP%20Servers/leadsmcp/docs/onboarding/WEBHOOK-PAYLOAD-EXAMPLES.md)

## Operational Notes

- Never commit live secrets to the repository.
- Treat `.env.example` as the only safe env file for customers.
- Keep customer-specific credentials out of issues, PRs, and release notes.
- If a customer needs stricter isolation, provide a repo fork or a dedicated
  deployment instance.
