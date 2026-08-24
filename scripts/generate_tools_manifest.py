#!/usr/bin/env python3
"""Regenerate tools.json from the live MCP tool registry.

Usage:
    python scripts/generate_tools_manifest.py          # write tools.json
    python scripts/generate_tools_manifest.py --check   # verify it is up to date

``--check`` exits non-zero if the committed tools.json differs from freshly
generated output, so CI can guard against manifest drift.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from servers.manifest import manifest_json, manifest_path, write_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify tools.json matches the live tool registry without writing.",
    )
    args = parser.parse_args()

    path = manifest_path()
    fresh = manifest_json()

    if args.check:
        if not path.exists():
            print(f"tools.json missing at {path}", file=sys.stderr)
            return 1
        current = path.read_text(encoding="utf-8")
        if current != fresh:
            print(
                "tools.json is out of date. Run: python scripts/generate_tools_manifest.py",
                file=sys.stderr,
            )
            return 1
        print("tools.json is up to date.")
        return 0

    write_manifest()
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
