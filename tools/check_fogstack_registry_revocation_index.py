#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a Fog Stack registry revocation index")
    parser.add_argument("--index", required=True, type=Path)
    args = parser.parse_args()

    index = load_json(args.index)
    errors: list[str] = []

    if index.get("kind") != "FogStackRegistryRevocationIndex":
        errors.append("revocation index kind mismatch")

    entries = index.get("entries")
    if not isinstance(entries, list):
        errors.append("entries must be a list")
    else:
        seen: set[tuple[str, str]] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append("entry is not an object")
                continue
            bundle_id = entry.get("bundle_id")
            version = entry.get("version")
            status = entry.get("status")
            if not isinstance(bundle_id, str) or not bundle_id:
                errors.append("entry missing bundle_id")
            if not isinstance(version, str) or not version:
                errors.append("entry missing version")
            if status not in {"revoked", "rollback"}:
                errors.append(f"invalid status: {status}")
            key = (str(bundle_id), str(version))
            if key in seen:
                errors.append(f"duplicate revocation entry: {bundle_id}@{version}")
            seen.add(key)

    if errors:
        for item in errors:
            print(item)
        return 1

    print("FogStack registry revocation index passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
