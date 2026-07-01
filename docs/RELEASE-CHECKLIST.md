# Release Checklist

Use this before publishing a new GitHub Release for customers.

## Code and Docs
- update version tag
- review README for drift
- update install docs if env vars or routes changed
- update migration notes if storage or auth behavior changed

## Security
- no live secrets in repo
- `.env` not committed
- examples sanitized
- customer data removed from screenshots and docs

## Functional Checks
- health endpoint passes
- MCP connection succeeds
- one GHL read succeeds
- one GHL write succeeds
- token refresh path succeeds
- custom pages load
- map UI loads if enabled

## Release Assets
- create git tag
- create GitHub Release
- include release notes
- include breaking changes if any
- include Docker image reference if applicable

## Customer Communication
- notify customers of new version
- include upgrade steps
- include rollback guidance if needed
