"""
Patches main.py to add a full OAuth 2.0 Authorization Server for custom connectors
(ChatGPT GPT Actions, Perplexity, etc.). Run once from the project root.
"""
import pathlib, re

path = pathlib.Path("main.py")
src = path.read_text(encoding="utf-8")

ANCHOR = 'def _oauth_redirect_uri(request: Request) -> str:\n    configured = os.getenv("GHL_OAUTH_REDIRECT_URI", "").strip()\n    if configured:'

assert ANCHOR in src, "Anchor not found — has main.py changed?"

HELPERS = '''
# ══════════════════════════════════════════════════════════════════════════════
# Custom Connector OAuth 2.0 Authorization Server
# Enables installation via ChatGPT GPT Actions, Perplexity custom connectors,
# and any OAuth 2.0 client that supports the authorization_code flow.
#
# Env vars:
#   CONNECTOR_CLIENTS          JSON: {client_id: {secret, name, redirect_uris:[]}}
#                              e.g. {"chatgpt":{"secret":"s3cr3t","name":"ChatGPT",
#                                    "redirect_uris":["https://chatgpt.com/aip/p-..."]}}
#   CONNECTOR_TOKEN_TTL        Access token TTL seconds (default 3600)
#   CONNECTOR_REFRESH_TTL      Refresh token TTL seconds (default 2592000 = 30d)
#   CONNECTOR_REQUIRE_CONSENT  Show HTML consent page before issuing code (default false)
#   CONNECTOR_TOKEN_STORE_PATH JSONL path (default /tmp/leadsmcp_connector_tokens.jsonl)
# ══════════════════════════════════════════════════════════════════════════════

def _connector_clients() -> dict:
    raw = os.getenv("CONNECTOR_CLIENTS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _connector_token_ttl() -> int:
    try:
        return max(60, int(os.getenv("CONNECTOR_TOKEN_TTL", "3600")))
    except ValueError:
        return 3600


def _connector_refresh_ttl() -> int:
    try:
        return max(300, int(os.getenv("CONNECTOR_REFRESH_TTL", "2592000")))
    except ValueError:
        return 2592000


def _connector_token_store_path() -> Path:
    return Path(os.getenv("CONNECTOR_TOKEN_STORE_PATH", "/tmp/leadsmcp_connector_tokens.jsonl").strip())


def _connector_token_cipher() -> Fernet:
    secret = _install_encryption_secret()
    if not secret:
        raise ValueError("Missing encryption secret for connector token store.")
    key = base64.urlsafe_b64encode(hashlib.sha256(("connector:" + secret).encode()).digest())
    return Fernet(key)


def _connector_token_encrypt(value: str) -> str:
    return _connector_token_cipher().encrypt(value.encode()).decode() if value else ""


def _connector_token_decrypt(value: str) -> str:
    return _connector_token_cipher().decrypt(value.encode()).decode() if value else ""


def _connector_load_tokens() -> list:
    path = _connector_token_store_path()
    if not path.exists():
        return []
    records = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except (json.JSONDecodeError, ValueError):
                        pass
    except OSError:
        pass
    return records


def _connector_persist_token(record: dict) -> None:
    path = _connector_token_store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\\n")
    except OSError:
        pass


def _connector_find_by_code(*, code: str) -> dict | None:
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    for record in _connector_load_tokens():
        if record.get("code_hash") == code_hash and record.get("type") == "code":
            return record
    return None


def _connector_find_token(*, access_token: str) -> dict | None:
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    for record in _connector_load_tokens():
        if record.get("token_hash") == token_hash:
            return record
    return None


def _connector_find_by_refresh(*, refresh_token: str) -> dict | None:
    rtoken_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    for record in _connector_load_tokens():
        if record.get("refresh_hash") == rtoken_hash:
            return record
    return None


def _connector_validate_client(*, client_id: str, client_secret: str) -> dict | None:
    clients = _connector_clients()
    client = clients.get(client_id)
    if not client:
        return None
    if not hmac.compare_digest(str(client.get("secret", "")), client_secret):
        return None
    return client


def _connector_validate_redirect_uri(*, client_id: str, redirect_uri: str) -> bool:
    clients = _connector_clients()
    client = clients.get(client_id)
    if not client:
        return False
    return redirect_uri in client.get("redirect_uris", [])


def _connector_issue_code_record(*, client_id: str, redirect_uri: str, scopes: list) -> dict:
    now = int(time.time())
    code = secrets.token_urlsafe(32)
    record = {
        "type": "code",
        "client_id": client_id,
        "code_hash": hashlib.sha256(code.encode()).hexdigest(),
        "code_enc": _connector_token_encrypt(code),
        "redirect_uri": redirect_uri,
        "scopes": scopes,
        "issued_at": now,
        "expires_at": now + 300,
    }
    _connector_persist_token(record)
    return {"code": code, "record": record}


def _connector_issue_token_record(*, client_id: str, scopes: list) -> dict:
    now = int(time.time())
    access_token = secrets.token_urlsafe(40)
    refresh_token = secrets.token_urlsafe(40)
    record = {
        "type": "token",
        "client_id": client_id,
        "token_hash": hashlib.sha256(access_token.encode()).hexdigest(),
        "refresh_hash": hashlib.sha256(refresh_token.encode()).hexdigest(),
        "access_token_enc": _connector_token_encrypt(access_token),
        "refresh_token_enc": _connector_token_encrypt(refresh_token),
        "scopes": scopes,
        "issued_at": now,
        "expires_at": now + _connector_token_ttl(),
        "refresh_expires_at": now + _connector_refresh_ttl(),
    }
    _connector_persist_token(record)
    return {"access_token": access_token, "refresh_token": refresh_token, "record": record}

'''

ROUTES = '''

# ── Connector: RFC 8414 metadata ──────────────────────────────────────────────
@orchestrator.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
async def connector_oauth_metadata(request: Request) -> JSONResponse:
    base = _public_base_url(request).rstrip("/")
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/connector/authorize",
        "token_endpoint": f"{base}/oauth/connector/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "scopes_supported": ["mcp"],
        "service_documentation": f"{base}/support",
    })


# ── Connector: MCP manifest ───────────────────────────────────────────────────
@orchestrator.custom_route("/.well-known/mcp.json", methods=["GET"])
async def connector_mcp_manifest(request: Request) -> JSONResponse:
    base = _public_base_url(request).rstrip("/")
    return JSONResponse({
        "schema_version": "1.0",
        "name_for_human": "LeadsMCP",
        "name_for_model": "leadsmcp",
        "description_for_human": "Live lead search, Google Maps business data, GoHighLevel CRM sync, and Stripe-gated export in one MCP server.",
        "description_for_model": "Search for businesses and leads via Outscraper/Google Maps, push contacts and opportunities into GoHighLevel CRM, and meter qualified lead exports through Stripe. Requires OAuth authentication.",
        "auth": {
            "type": "oauth",
            "authorization_url": f"{base}/oauth/connector/authorize",
            "token_url": f"{base}/oauth/connector/token",
            "scope": "mcp",
        },
        "api": {"type": "mcp", "url": f"{base}/mcp"},
        "contact_email": os.getenv("LEADSMCP_CONTACT_EMAIL", "") or None,
        "legal_info_url": f"{base}/support",
    })


# ── Connector: Authorization endpoint ─────────────────────────────────────────
@orchestrator.custom_route("/oauth/connector/authorize", methods=["GET"])
async def connector_oauth_authorize(request: Request) -> Response:
    client_id = request.query_params.get("client_id", "").strip()
    redirect_uri = request.query_params.get("redirect_uri", "").strip()
    state = request.query_params.get("state", "").strip()
    scope = request.query_params.get("scope", "mcp").strip()
    response_type = request.query_params.get("response_type", "code").strip()

    if response_type != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)

    clients = _connector_clients()
    if not client_id or client_id not in clients:
        return JSONResponse(
            {"error": "invalid_client", "error_description": f"Unknown client_id: {client_id!r}. Register in CONNECTOR_CLIENTS."},
            status_code=400,
        )
    if not redirect_uri:
        return JSONResponse({"error": "invalid_request", "error_description": "redirect_uri is required."}, status_code=400)
    if not _connector_validate_redirect_uri(client_id=client_id, redirect_uri=redirect_uri):
        return JSONResponse({"error": "invalid_redirect_uri", "error_description": "redirect_uri not registered for this client."}, status_code=400)

    scopes = [s for s in scope.split() if s]
    client_name = clients[client_id].get("name", client_id)
    require_consent = _truthy(os.getenv("CONNECTOR_REQUIRE_CONSENT", "false"))

    if require_consent:
        base = _public_base_url(request).rstrip("/")
        approve_url = _append_query_params(
            f"{base}/oauth/connector/approve",
            {"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "scope": scope},
        )
        deny_url = _append_query_params(redirect_uri, {"error": "access_denied", "state": state})
        body = f"""<div class="wrap stack"><section class="panel stack">
        <span class="kicker">Connect</span>
        <h1>{client_name} wants to connect to LeadsMCP</h1>
        <p>This grants <strong>{client_name}</strong> access to your LeadsMCP tools: lead search, CRM sync, and data export.</p>
        <div class="nav-links">
          <a class="btn primary" href="{approve_url}">Approve</a>
          <a class="btn" href="{deny_url}">Deny</a>
        </div></section></div>"""
        return HTMLResponse(_html_shell(title=f"Connect {client_name} to LeadsMCP", body=body))

    result = _connector_issue_code_record(client_id=client_id, redirect_uri=redirect_uri, scopes=scopes)
    params: dict = {"code": result["code"]}
    if state:
        params["state"] = state
    return RedirectResponse(url=_append_query_params(redirect_uri, params), status_code=302)


# ── Connector: Consent approval (used only when CONNECTOR_REQUIRE_CONSENT=true) ─
@orchestrator.custom_route("/oauth/connector/approve", methods=["GET"])
async def connector_oauth_approve(request: Request) -> Response:
    client_id = request.query_params.get("client_id", "").strip()
    redirect_uri = request.query_params.get("redirect_uri", "").strip()
    state = request.query_params.get("state", "").strip()
    scope = request.query_params.get("scope", "mcp").strip()

    clients = _connector_clients()
    if not client_id or client_id not in clients:
        return JSONResponse({"error": "invalid_client"}, status_code=400)
    if not redirect_uri or not _connector_validate_redirect_uri(client_id=client_id, redirect_uri=redirect_uri):
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)

    scopes = [s for s in scope.split() if s]
    result = _connector_issue_code_record(client_id=client_id, redirect_uri=redirect_uri, scopes=scopes)
    params: dict = {"code": result["code"]}
    if state:
        params["state"] = state
    return RedirectResponse(url=_append_query_params(redirect_uri, params), status_code=302)


# ── Connector: Token endpoint ──────────────────────────────────────────────────
@orchestrator.custom_route("/oauth/connector/token", methods=["POST"])
async def connector_oauth_token(request: Request) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body: dict = await request.json()
        except Exception:
            body = {}
    else:
        form = await request.form()
        body = {k: str(v) for k, v in form.items()}

    grant_type = body.get("grant_type", "").strip()
    client_id = body.get("client_id", "").strip()
    client_secret = body.get("client_secret", "").strip()

    if not client_id or not client_secret:
        return JSONResponse({"error": "invalid_client", "error_description": "client_id and client_secret are required."}, status_code=401)

    client = _connector_validate_client(client_id=client_id, client_secret=client_secret)
    if not client:
        return JSONResponse({"error": "invalid_client", "error_description": "Invalid client credentials."}, status_code=401)

    now = int(time.time())

    if grant_type == "authorization_code":
        code = body.get("code", "").strip()
        redirect_uri = body.get("redirect_uri", "").strip()
        if not code:
            return JSONResponse({"error": "invalid_request", "error_description": "code is required."}, status_code=400)

        code_record = _connector_find_by_code(code=code)
        if not code_record:
            return JSONResponse({"error": "invalid_grant", "error_description": "Code not found or already used."}, status_code=400)
        if code_record.get("client_id") != client_id:
            return JSONResponse({"error": "invalid_grant", "error_description": "Code was not issued to this client."}, status_code=400)
        if now > code_record.get("expires_at", 0):
            return JSONResponse({"error": "invalid_grant", "error_description": "Authorization code has expired."}, status_code=400)
        if redirect_uri and code_record.get("redirect_uri") != redirect_uri:
            return JSONResponse({"error": "invalid_grant", "error_description": "redirect_uri mismatch."}, status_code=400)

        issued = _connector_issue_token_record(client_id=client_id, scopes=code_record.get("scopes", []))
        return JSONResponse({
            "access_token": issued["access_token"],
            "refresh_token": issued["refresh_token"],
            "token_type": "bearer",
            "expires_in": _connector_token_ttl(),
            "scope": " ".join(code_record.get("scopes", ["mcp"])),
        })

    elif grant_type == "refresh_token":
        refresh_token = body.get("refresh_token", "").strip()
        if not refresh_token:
            return JSONResponse({"error": "invalid_request", "error_description": "refresh_token is required."}, status_code=400)

        rrecord = _connector_find_by_refresh(refresh_token=refresh_token)
        if not rrecord:
            return JSONResponse({"error": "invalid_grant", "error_description": "Refresh token not found."}, status_code=400)
        if rrecord.get("client_id") != client_id:
            return JSONResponse({"error": "invalid_grant", "error_description": "Refresh token not issued to this client."}, status_code=400)
        if now > rrecord.get("refresh_expires_at", 0):
            return JSONResponse({"error": "invalid_grant", "error_description": "Refresh token has expired."}, status_code=400)

        issued = _connector_issue_token_record(client_id=client_id, scopes=rrecord.get("scopes", []))
        return JSONResponse({
            "access_token": issued["access_token"],
            "refresh_token": issued["refresh_token"],
            "token_type": "bearer",
            "expires_in": _connector_token_ttl(),
            "scope": " ".join(rrecord.get("scopes", ["mcp"])),
        })

    else:
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

'''

# Insert helpers before GHL oauth helpers
src = src.replace(ANCHOR, HELPERS + ANCHOR, 1)

# Insert routes before /health
HEALTH_ANCHOR = "# ── Health check ─"
assert HEALTH_ANCHOR in src, "Health anchor not found"
src = src.replace(HEALTH_ANCHOR, ROUTES + "\n\n" + HEALTH_ANCHOR, 1)

# Add new paths to MCPSecretMiddleware bypass list
OLD_BYPASS = '"/oauth/ghl/callback",'
NEW_BYPASS = '''"/.well-known/oauth-authorization-server",
            "/.well-known/mcp.json",
            "/oauth/connector/authorize",
            "/oauth/connector/approve",
            "/oauth/connector/token",
            "/oauth/ghl/callback",'''
src = src.replace(OLD_BYPASS, NEW_BYPASS, 1)

# Add connector bearer token check to MCPSecretMiddleware
OLD_SECRET_CHECK = '        provided_secret = request.headers.get("x-mcp-secret", "").strip()\n        if not provided_secret or provided_secret != required_secret:'
NEW_SECRET_CHECK = '''        # Allow valid connector bearer tokens through without x-mcp-secret
        auth_header = request.headers.get("authorization", "").strip()
        if auth_header.lower().startswith("bearer "):
            bearer = auth_header[7:].strip()
            token_record = _connector_find_token(access_token=bearer)
            if token_record and int(time.time()) < token_record.get("expires_at", 0):
                return await call_next(request)

        provided_secret = request.headers.get("x-mcp-secret", "").strip()
        if not provided_secret or provided_secret != required_secret:'''
src = src.replace(OLD_SECRET_CHECK, NEW_SECRET_CHECK, 1)

path.write_text(src, encoding="utf-8")
print("✅  Patch applied successfully.")
print(f"   _connector_clients references: {src.count('_connector_clients')}")
print(f"   connector routes registered:   {src.count('/oauth/connector/')}")
print(f"   well-known endpoints:          {src.count('well-known')}")
