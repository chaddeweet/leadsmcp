"""Supabase-backed OAuth 2.0 / DCR authorization server for MCP custom connectors.

Enables installation of the LeadsMCP `/mcp` endpoint via ChatGPT and Perplexity
custom connectors (and any RFC 6749 / RFC 8414 / RFC 7591 / RFC 9728 client).

Why Supabase and not a local file:
    On serverless (Vercel) the authorize, token, and `/mcp` requests each run in a
    separate, ephemeral function invocation with a non-shared `/tmp`. A file-based
    token store therefore loses the authorization code before the token exchange and
    loses the access token before `/mcp` validates it. Persisting to Supabase
    (via its PostgREST REST API over httpx — no extra dependency) makes the flow work
    across invocations.

Storage:
    A single `connector_oauth` table holds three record kinds (`client`, `code`,
    `token`), looked up by indexed hash columns. Codes and access/refresh tokens are
    never stored in plaintext: only a SHA-256 lookup hash and a Fernet-encrypted copy
    are persisted. Client secrets are stored as SHA-256 hashes and compared in
    constant time. When Supabase is not configured an in-process store is used so the
    flow still works for local development and tests (not durable across processes).

Env vars (names only — never commit values):
    SUPABASE_URL                Project URL, e.g. https://xxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY   Service-role key (server-side only; bypasses RLS)
    SUPABASE_OAUTH_TABLE        Table name (default "connector_oauth")
    CONNECTOR_OAUTH_ENABLED     Force-enable even without Supabase (default: auto)
    CONNECTOR_DCR_ENABLED       Allow Dynamic Client Registration (default true)
    CONNECTOR_CLIENTS           Legacy static clients JSON (kept for back-compat)
    CONNECTOR_TOKEN_TTL         Access-token TTL seconds (default 3600)
    CONNECTOR_REFRESH_TTL       Refresh-token TTL seconds (default 2592000 = 30d)
    CONNECTOR_SCOPES_SUPPORTED  Space-separated scopes (default "mcp")
    GHL_INSTALL_ENCRYPTION_SECRET / GHL_OAUTH_STATE_SECRET / MCP_SECRET
                                Fernet key material (first non-empty wins)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

import httpx
from cryptography.fernet import Fernet

DEFAULT_TABLE = "connector_oauth"
CODE_TTL_SECONDS = 300


class StoreError(Exception):
    """Raised when the persistence backend rejects or cannot serve a request.

    Carries the upstream (PostgREST) HTTP status and a short, non-secret detail
    string so route handlers can return a structured error instead of an opaque
    500. The detail is the PostgREST error body (e.g. "permission denied for
    table connector_oauth") — safe to surface; it never contains credentials or
    the Supabase project URL.
    """

    def __init__(self, status: int, detail: str = "") -> None:
        super().__init__(detail or f"store error {status}")
        self.status = status
        self.detail = detail


# ── Configuration helpers ─────────────────────────────────────────────────────
def _supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "").strip().rstrip("/")


def _supabase_key() -> str:
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )


def _supabase_table() -> str:
    return os.getenv("SUPABASE_OAUTH_TABLE", DEFAULT_TABLE).strip() or DEFAULT_TABLE


def _supabase_configured() -> bool:
    return bool(_supabase_url() and _supabase_key())


def _durable_store_required(env: dict[str, str] | None = None) -> bool:
    """Production connector grants must never use process memory."""
    values = env or os.environ
    return (
        values.get("VERCEL_ENV", "").strip().lower() == "production"
        or values.get("ENVIRONMENT", "").strip().lower() == "production"
    )


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def connector_oauth_enabled() -> bool:
    """Whether the connector OAuth surface should be served and enforced.

    Enabled when explicitly turned on, when Supabase is configured, or when legacy
    static clients are present. Defaults off so existing x-mcp-secret-only
    deployments are unaffected until they opt in.
    """
    override = os.getenv("CONNECTOR_OAUTH_ENABLED", "").strip()
    if override:
        return _truthy(override)
    return _supabase_configured() or bool(_static_clients())


def dcr_enabled() -> bool:
    return _truthy(os.getenv("CONNECTOR_DCR_ENABLED", "true"))


def token_ttl() -> int:
    try:
        return max(60, int(os.getenv("CONNECTOR_TOKEN_TTL", "3600")))
    except ValueError:
        return 3600


def refresh_ttl() -> int:
    try:
        return max(300, int(os.getenv("CONNECTOR_REFRESH_TTL", "2592000")))
    except ValueError:
        return 2592000


def scopes_supported() -> list[str]:
    raw = os.getenv("CONNECTOR_SCOPES_SUPPORTED", "mcp").strip()
    return [s for s in raw.split() if s] or ["mcp"]


def _static_clients() -> dict[str, Any]:
    raw = os.getenv("CONNECTOR_CLIENTS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


# ── Crypto helpers ────────────────────────────────────────────────────────────
def _encryption_secret() -> str:
    return (
        os.getenv("GHL_INSTALL_ENCRYPTION_SECRET", "").strip()
        or os.getenv("GHL_OAUTH_STATE_SECRET", "").strip()
        or os.getenv("MCP_SECRET", "").strip()
    )


def _cipher() -> Fernet:
    secret = _encryption_secret()
    if not secret:
        raise ValueError(
            "Missing encryption secret for connector OAuth store. Set "
            "GHL_INSTALL_ENCRYPTION_SECRET (or GHL_OAUTH_STATE_SECRET / MCP_SECRET)."
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(("connector:" + secret).encode()).digest())
    return Fernet(key)


def _encrypt(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode() if value else ""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _b64url_no_pad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def verify_pkce(*, code_verifier: str, code_challenge: str, method: str) -> bool:
    """RFC 7636 PKCE verification. Supports S256 (preferred) and plain."""
    if not code_challenge:
        return True  # no challenge was bound to the code
    if not code_verifier:
        return False
    method = (method or "plain").upper()
    if method == "S256":
        expected = _b64url_no_pad(hashlib.sha256(code_verifier.encode()).digest())
        return hmac.compare_digest(expected, code_challenge)
    if method == "PLAIN":
        return hmac.compare_digest(code_verifier, code_challenge)
    return False


# ── Storage backends ──────────────────────────────────────────────────────────
class _MemoryStore:
    """In-process fallback store. Not durable across processes/invocations."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    async def insert(self, row: dict[str, Any]) -> None:
        self._rows.append(dict(row))

    async def _find(self, **match: Any) -> dict[str, Any] | None:
        for row in self._rows:
            if all(row.get(k) == v for k, v in match.items()):
                return dict(row)
        return None

    async def find_client(self, client_id: str) -> dict[str, Any] | None:
        return await self._find(kind="client", client_id=client_id)

    async def find_code(self, code_hash: str) -> dict[str, Any] | None:
        return await self._find(kind="code", code_hash=code_hash)

    async def find_token(self, token_hash: str) -> dict[str, Any] | None:
        return await self._find(kind="token", token_hash=token_hash)

    async def find_refresh(self, refresh_hash: str) -> dict[str, Any] | None:
        return await self._find(kind="token", refresh_hash=refresh_hash)

    async def delete_code(self, code_hash: str) -> None:
        self._rows = [r for r in self._rows if not (r.get("kind") == "code" and r.get("code_hash") == code_hash)]


def _postgrest_detail(resp: "httpx.Response") -> str:
    """Extract a short, non-secret error message from a PostgREST error body."""
    try:
        body = resp.json()
    except (ValueError, json.JSONDecodeError):
        return (resp.text or "").strip()[:300]
    if isinstance(body, dict):
        for key in ("message", "hint", "details", "error", "code"):
            val = body.get(key)
            if isinstance(val, str) and val:
                return val[:300]
    return str(body)[:300]


class _SupabaseStore:
    """Supabase PostgREST-backed store using the service-role key."""

    def __init__(self) -> None:
        self._base = f"{_supabase_url()}/rest/v1/{_supabase_table()}"
        key = _supabase_key()
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def insert(self, row: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._base,
                    headers={**self._headers, "Prefer": "return=minimal"},
                    json=row,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StoreError(exc.response.status_code, _postgrest_detail(exc.response)) from exc
        except httpx.RequestError as exc:
            raise StoreError(503, f"Supabase unreachable: {type(exc).__name__}") from exc

    async def _select_one(self, params: dict[str, str]) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self._base,
                    headers=self._headers,
                    params={**params, "limit": "1"},
                )
                resp.raise_for_status()
                rows = resp.json()
        except httpx.HTTPStatusError as exc:
            raise StoreError(exc.response.status_code, _postgrest_detail(exc.response)) from exc
        except httpx.RequestError as exc:
            raise StoreError(503, f"Supabase unreachable: {type(exc).__name__}") from exc
        return rows[0] if isinstance(rows, list) and rows else None

    async def find_client(self, client_id: str) -> dict[str, Any] | None:
        return await self._select_one({"kind": "eq.client", "client_id": f"eq.{client_id}"})

    async def find_code(self, code_hash: str) -> dict[str, Any] | None:
        return await self._select_one({"kind": "eq.code", "code_hash": f"eq.{code_hash}"})

    async def find_token(self, token_hash: str) -> dict[str, Any] | None:
        return await self._select_one({"kind": "eq.token", "token_hash": f"eq.{token_hash}"})

    async def find_refresh(self, refresh_hash: str) -> dict[str, Any] | None:
        return await self._select_one({"kind": "eq.token", "refresh_hash": f"eq.{refresh_hash}"})

    async def delete_code(self, code_hash: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    self._base,
                    headers=self._headers,
                    params={"kind": "eq.code", "code_hash": f"eq.{code_hash}"},
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StoreError(exc.response.status_code, _postgrest_detail(exc.response)) from exc
        except httpx.RequestError as exc:
            raise StoreError(503, f"Supabase unreachable: {type(exc).__name__}") from exc


_memory_singleton = _MemoryStore()


def get_store() -> Any:
    if _supabase_configured():
        return _SupabaseStore()
    if _durable_store_required():
        raise StoreError(
            503,
            "Connector OAuth requires Supabase in production. Configure "
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
        )
    return _memory_singleton


# ── Client resolution (static env clients + dynamically registered) ───────────
async def resolve_client(client_id: str) -> dict[str, Any] | None:
    """Return a normalized client descriptor, or None.

    Descriptor keys: client_id, redirect_uris(list), secret_hash(str|""),
    token_endpoint_auth_method, name.
    """
    if not client_id:
        return None

    static = _static_clients().get(client_id)
    if static:
        secret = str(static.get("secret", ""))
        return {
            "client_id": client_id,
            "redirect_uris": list(static.get("redirect_uris", [])),
            "secret_hash": _sha256(secret) if secret else "",
            "token_endpoint_auth_method": "client_secret_post" if secret else "none",
            "name": static.get("name", client_id),
        }

    row = await get_store().find_client(client_id)
    if not row:
        return None
    data = row.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            data = {}
    return {
        "client_id": client_id,
        "redirect_uris": list(data.get("redirect_uris", [])),
        "secret_hash": str(data.get("secret_hash", "")),
        "token_endpoint_auth_method": data.get("token_endpoint_auth_method", "none"),
        "name": data.get("client_name", client_id),
    }


def validate_client_secret(client: dict[str, Any], provided_secret: str) -> bool:
    expected = client.get("secret_hash", "")
    if not expected:
        return False
    return hmac.compare_digest(expected, _sha256(provided_secret or ""))


def redirect_uri_registered(client: dict[str, Any], redirect_uri: str) -> bool:
    return redirect_uri in client.get("redirect_uris", [])


# ── Dynamic Client Registration (RFC 7591) ────────────────────────────────────
async def register_client(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    redirect_uris = body.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not redirect_uris or not all(isinstance(u, str) for u in redirect_uris):
        return 400, {
            "error": "invalid_redirect_uri",
            "error_description": "redirect_uris must be a non-empty array of strings.",
        }

    auth_method = str(body.get("token_endpoint_auth_method", "client_secret_post")).strip() or "client_secret_post"
    if auth_method not in {"none", "client_secret_post", "client_secret_basic"}:
        return 400, {
            "error": "invalid_client_metadata",
            "error_description": f"Unsupported token_endpoint_auth_method: {auth_method!r}.",
        }

    now = int(time.time())
    client_id = "dcr_" + secrets.token_urlsafe(24)
    client_secret = "" if auth_method == "none" else secrets.token_urlsafe(40)

    grant_types = body.get("grant_types") or ["authorization_code", "refresh_token"]
    response_types = body.get("response_types") or ["code"]
    client_name = str(body.get("client_name", "") or "")[:200]
    scope = str(body.get("scope", "") or " ".join(scopes_supported()))

    stored = {
        "kind": "client",
        "client_id": client_id,
        "data": {
            "redirect_uris": redirect_uris,
            "secret_hash": _sha256(client_secret) if client_secret else "",
            "token_endpoint_auth_method": auth_method,
            "grant_types": grant_types,
            "response_types": response_types,
            "client_name": client_name,
            "scope": scope,
            "created_at": now,
        },
        "created_at": now,
    }
    await get_store().insert(stored)

    response: dict[str, Any] = {
        "client_id": client_id,
        "client_id_issued_at": now,
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": auth_method,
        "grant_types": grant_types,
        "response_types": response_types,
        "scope": scope,
    }
    if client_name:
        response["client_name"] = client_name
    if client_secret:
        response["client_secret"] = client_secret
        response["client_secret_expires_at"] = 0  # never expires
    return 201, response


# ── Authorization codes and tokens ────────────────────────────────────────────
async def issue_code(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: list[str],
    code_challenge: str = "",
    code_challenge_method: str = "",
    installation: dict[str, str] | None = None,
) -> str:
    now = int(time.time())
    code = secrets.token_urlsafe(32)
    await get_store().insert(
        {
            "kind": "code",
            "client_id": client_id,
            "code_hash": _sha256(code),
            "data": {
                "code_enc": _encrypt(code),
                "redirect_uri": redirect_uri,
                "scopes": scopes,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                "installation": installation or {},
            },
            "expires_at": now + CODE_TTL_SECONDS,
            "created_at": now,
        }
    )
    return code


async def issue_token(
    *,
    client_id: str,
    scopes: list[str],
    installation: dict[str, str] | None = None,
) -> dict[str, str]:
    now = int(time.time())
    access_token = secrets.token_urlsafe(40)
    refresh_token = secrets.token_urlsafe(40)
    await get_store().insert(
        {
            "kind": "token",
            "client_id": client_id,
            "token_hash": _sha256(access_token),
            "refresh_hash": _sha256(refresh_token),
            "data": {
                "access_token_enc": _encrypt(access_token),
                "refresh_token_enc": _encrypt(refresh_token),
                "scopes": scopes,
                "installation": installation or {},
            },
            "expires_at": now + token_ttl(),
            "refresh_expires_at": now + refresh_ttl(),
            "created_at": now,
        }
    )
    return {"access_token": access_token, "refresh_token": refresh_token}


async def consume_code(*, code: str) -> dict[str, Any] | None:
    """Return the (still-valid) code record and delete it (single use)."""
    store = get_store()
    record = await store.find_code(_sha256(code))
    if not record:
        return None
    await store.delete_code(_sha256(code))
    if int(time.time()) > int(record.get("expires_at", 0)):
        return None
    return record


async def find_refresh_record(*, refresh_token: str) -> dict[str, Any] | None:
    record = await get_store().find_refresh(_sha256(refresh_token))
    if not record:
        return None
    if int(time.time()) > int(record.get("refresh_expires_at", 0)):
        return None
    return record


async def validate_bearer(access_token: str) -> dict[str, Any] | None:
    """Return the token record if the bearer is a valid, unexpired access token."""
    if not access_token:
        return None
    try:
        record = await get_store().find_token(_sha256(access_token))
    except StoreError:
        return None  # fail closed: a store outage must not authenticate a bearer
    if not record:
        return None
    if int(time.time()) > int(record.get("expires_at", 0)):
        return None
    return record


def _code_field(record: dict[str, Any], key: str, default: Any = None) -> Any:
    data = record.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            data = {}
    return data.get(key, default)


# ── Metadata documents ────────────────────────────────────────────────────────
def authorization_server_metadata(base: str) -> dict[str, Any]:
    base = base.rstrip("/")
    doc = {
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "token_endpoint_auth_methods_supported": [
            "none",
            "client_secret_post",
            "client_secret_basic",
        ],
        "scopes_supported": scopes_supported(),
        "service_documentation": f"{base}/support",
    }
    if dcr_enabled():
        doc["registration_endpoint"] = f"{base}/register"
    return doc


def protected_resource_metadata(base: str) -> dict[str, Any]:
    base = base.rstrip("/")
    return {
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
        "scopes_supported": scopes_supported(),
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{base}/support",
    }


def protected_resource_metadata_url(base: str) -> str:
    return f"{base.rstrip('/')}/.well-known/oauth-protected-resource"


def www_authenticate_challenge(base: str, *, error: str = "", description: str = "") -> str:
    """RFC 9728 WWW-Authenticate challenge pointing MCP clients at DCR discovery."""
    parts = [f'Bearer resource_metadata="{protected_resource_metadata_url(base)}"']
    if error:
        parts.append(f'error="{error}"')
    if description:
        parts.append(f'error_description="{description}"')
    return ", ".join(parts)
