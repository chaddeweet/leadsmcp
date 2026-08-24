import connector_oauth
import pytest


@pytest.mark.asyncio
async def test_installation_binding_survives_code_and_token_exchange(monkeypatch):
    store = connector_oauth._MemoryStore()
    monkeypatch.setattr(connector_oauth, "get_store", lambda: store)
    binding = {
        "install_key": "company:location",
        "company_id": "company",
        "location_id": "location",
    }

    code = await connector_oauth.issue_code(
        client_id="client",
        redirect_uri="https://client.example/callback",
        scopes=["mcp"],
        installation=binding,
    )
    code_record = await connector_oauth.consume_code(code=code)
    assert code_record["data"]["installation"] == binding

    issued = await connector_oauth.issue_token(
        client_id="client",
        scopes=["mcp"],
        installation=binding,
    )
    token_record = await connector_oauth.validate_bearer(
        issued["access_token"]
    )
    assert token_record["data"]["installation"] == binding

