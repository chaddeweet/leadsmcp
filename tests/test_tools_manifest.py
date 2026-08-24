"""Ensure tools.json stays consistent with the live MCP tool registry."""
import json

from servers.manifest import build_manifest, manifest_json, manifest_path


def test_manifest_file_exists():
    assert manifest_path().exists(), "run: python scripts/generate_tools_manifest.py"


def test_manifest_matches_registry():
    committed = manifest_path().read_text(encoding="utf-8")
    fresh = manifest_json()
    assert committed == fresh, (
        "tools.json is out of date; regenerate with "
        "python scripts/generate_tools_manifest.py"
    )


def test_manifest_covers_all_servers():
    manifest = build_manifest()
    servers = {t["server"] for t in manifest["tools"]}
    assert servers == {"outscraper", "stripe", "tempmail"}
    assert manifest["tool_count"] == len(manifest["tools"])


def test_every_tool_has_name_description_and_schemas():
    manifest = build_manifest()
    for tool in manifest["tools"]:
        assert tool["name"]
        assert tool["description"], f"{tool['name']} missing description"
        assert tool["input_schema"].get("type") == "object"
        assert isinstance(tool["output_schema"], dict)


def test_manifest_names_are_namespaced_and_unique():
    manifest = build_manifest()
    names = [t["name"] for t in manifest["tools"]]
    assert len(names) == len(set(names))
    for tool in manifest["tools"]:
        assert tool["name"] == f"{tool['server']}_{tool['local_name']}"
