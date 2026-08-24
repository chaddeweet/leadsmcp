from pathlib import Path

import pytest

import ghl_install_store


def test_marketplace_mode_rejects_file_backend():
    with pytest.raises(ghl_install_store.InstallStoreError, match="required"):
        ghl_install_store.install_store_backend(
            {
                "LEADSMCP_MODE": "marketplace",
                "GHL_INSTALL_STORE_BACKEND": "file",
            }
        )


def test_developer_mode_allows_file_backend():
    assert (
        ghl_install_store.install_store_backend(
            {
                "LEADSMCP_MODE": "developer",
                "GHL_INSTALL_STORE_BACKEND": "file",
            }
        )
        == "file"
    )


@pytest.mark.asyncio
async def test_developer_file_store_writes_record(monkeypatch, tmp_path: Path):
    path = tmp_path / "installs.jsonl"
    monkeypatch.setenv("LEADSMCP_MODE", "developer")
    monkeypatch.setenv("GHL_INSTALL_STORE_BACKEND", "file")
    monkeypatch.setenv("GHL_INSTALL_STORE_PATH", str(path))

    result = await ghl_install_store.persist_install_record(
        {"install_key": "company:location", "installed": True}
    )

    assert result["backend"] == "file"
    assert '"install_key":"company:location"' in path.read_text()
