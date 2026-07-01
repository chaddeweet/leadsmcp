# Create the Public LeadsMCP GitHub Repo

Use this guide to spin the public-facing GitHub repo out of the private product repo.

## Goal

Create a clean public repository that markets LeadsMCP without exposing the private server implementation.

## Include These Files

Copy these files and folders into the public repo root:

- `distribution/public-repo-starter/README.md` -> `README.md`
- `distribution/public-repo-starter/SUPPORT.md` -> `SUPPORT.md`
- `distribution/public-repo-starter/SECURITY.md` -> `SECURITY.md`
- `distribution/public-repo-starter/docs/` -> `docs/`
- `distribution/public-repo-starter/.github/ISSUE_TEMPLATE/config.yml` -> `.github/ISSUE_TEMPLATE/config.yml`

## Do Not Include

Do not copy:
- `main.py`
- `agent.py`
- `servers/`
- `.env.example` unless you explicitly want public env docs
- customer-only deployment docs
- release artifacts intended for licensed customers
- any credentials, redirect URLs, or customer screenshots containing sensitive info

## Suggested Repo Name

One of:
- `leadsmcp`
- `leadsmcp-docs`
- `leadsmcp-public`

## Suggested First Commit

```bash
mkdir leadsmcp-public
cd leadsmcp-public
mkdir -p docs .github/ISSUE_TEMPLATE
cp "/path/to/private/leadsmcp/distribution/public-repo-starter/README.md" README.md
cp "/path/to/private/leadsmcp/distribution/public-repo-starter/SUPPORT.md" SUPPORT.md
cp "/path/to/private/leadsmcp/distribution/public-repo-starter/SECURITY.md" SECURITY.md
cp -R "/path/to/private/leadsmcp/distribution/public-repo-starter/docs/." docs/
cp "/path/to/private/leadsmcp/distribution/public-repo-starter/.github/ISSUE_TEMPLATE/config.yml" .github/ISSUE_TEMPLATE/config.yml
git init
git add .
git commit -m "Create public LeadsMCP documentation repo"
```

## Good Next Additions

After the public repo exists, add:
- screenshots of the search workspace
- install JSON examples
- a simple architecture diagram
- changelog summaries linked to private release versions
- contact and demo links
