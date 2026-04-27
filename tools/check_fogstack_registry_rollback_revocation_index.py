#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical_digest(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def check_entry(registry_root: Path, entry: dict[str, Any], errors: list[str]) -> None:
    pointer_ref = entry.get("pointer_ref")
    pointer_digest = entry.get("pointer_digest")
    bundle_id = entry.get("bundle_id")
    version = entry.get("version")
    if not isinstance(pointer_ref, str):
        errors.append("pointer_ref missing")
        return
    pointer_path = registry_root / pointer_ref
    if not pointer_path.exists():
        errors.append(f"pointer missing: {pointer_path}")
        return
    if pointer_digest != sha256_file(pointer_path):
        errors.append(f"pointer digest mismatch: {pointer_path}")
    pointer = load_json(pointer_path)
    if pointer.get("bundle_id") != bundle_id or pointer.get("version") != version:
        errors.append(f"pointer identity mismatch: {pointer_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Fog Stack registry rollback/revocation index")
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--index", type=Path, default=None)
    args = parser.parse_args()

    index_path = args.index or (args.registry_root / "rollback-revocation.index.json")
    if not index_path.exists():
        print(f"rollback/revocation index missing: {index_path}")
        return 1

    errors: list[str] = []
    index = load_json(index_path)
    if index.get("kind") != "FogStackRegistryRollbackRevocationIndex":
        errors.append("index kind mismatch")

    digest_material = dict(index)
    digest_material["index_digest"] = None
    if index.get("index_digest") != canonical_digest(digest_material):
        errors.append("index digest mismatch")

    rollback_targets = index.get("rollback_targets") or []
    revocations = index.get("revocations") or []
    if not isinstance(rollback_targets, list):
        errors.append("rollback_targets is not a list")
        rollback_targets = []
    if not isinstance(revocations, list):
        errors.append("revocations is not a list")
        revocations = []

    revoked_identities = set()
    for entry in revocations:
        if not isinstance(entry, dict):
            errors.append("revocation entry is not an object")
            continue
        check_entry(args.registry_root, entry, errors)
        revoked_identities.add((entry.get("bundle_id"), entry.get("version")))

    for entry in rollback_targets:
        if not isinstance(entry, dict):
            errors.append("rollback entry is not an object")
            continue
        check_entry(args.registry_root, entry, errors)
        if (entry.get("bundle_id"), entry.get("version")) in revoked_identities:
            errors.append(f"release cannot be both rollback target and revoked: {entry.get('bundle_id')} {entry.get('version')}")

    signatures = index.get("signatures") or []
    if not isinstance(signatures, list) or not signatures:
        errors.append("index signatures missing")

    if errors:
        for item in errors:
            print(item)
        return 1

    print("FogStack registry rollback/revocation index passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
