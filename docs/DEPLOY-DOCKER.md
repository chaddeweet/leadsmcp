# Deploy LeadsMCP with Docker

## Build

```bash
docker build -t leadsmcp .
```

## Run

```bash
docker run --rm -p 8000:8000 --env-file .env leadsmcp
```

## Verify

Open:
- `http://localhost:8000/`
- `http://localhost:8000/health`
- `http://localhost:8000/mcp`

## Production Notes

- Use a real Postgres database for install storage.
- Do not rely on filesystem persistence for token refresh state.
- Run behind HTTPS in production.
- Ensure GHL callback URLs point to the public HTTPS domain.
