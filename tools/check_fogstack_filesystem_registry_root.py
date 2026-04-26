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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a Fog Stack filesystem registry root")
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root_path = args.root or (args.registry_root / "registry-root.json")
    errors: list[str] = []
    if not root_path.exists():
        print(f"registry root missing: {root_path}")
        return 1

    root = load_json(root_path)
    if root.get("kind") != "FogStackFilesystemRegistryRoot":
        errors.append("registry root kind mismatch")

    expected_digest_material = dict(root)
    expected_digest_material["root_digest"] = None
    if root.get("root_digest") != canonical_digest(expected_digest_material):
        errors.append("registry root digest mismatch")

    releases = root.get("releases") or []
    if not isinstance(releases, list) or not releases:
        errors.append("registry root releases missing")
        releases = []

    for release in releases:
        if not isinstance(release, dict):
            errors.append("registry root release entry is not an object")
            continue
        pointer_ref = release.get("pointer_ref")
        index_ref = release.get("index_ref")
        if not isinstance(pointer_ref, str) or not isinstance(index_ref, str):
            errors.append("registry root release refs missing")
            continue
        pointer_path = args.registry_root / pointer_ref
        index_path = args.registry_root / index_ref
        if not pointer_path.exists():
            errors.append(f"release pointer missing: {pointer_path}")
            continue
        if not index_path.exists():
            errors.append(f"release index missing: {index_path}")
            continue
        if release.get("pointer_digest") != sha256_file(pointer_path):
            errors.append(f"release pointer digest mismatch: {pointer_path}")
        if release.get("index_digest") != sha256_file(index_path):
            errors.append(f"release index digest mismatch: {index_path}")
        pointer = load_json(pointer_path)
        if pointer.get("index_digest") != sha256_file(index_path):
            errors.append(f"pointer index digest mismatch: {pointer_path}")
        if pointer.get("bundle_id") != release.get("bundle_id") or pointer.get("version") != release.get("version"):
            errors.append(f"release identity mismatch: {pointer_path}")

    signatures = root.get("signatures") or []
    if not isinstance(signatures, list) or not signatures:
        errors.append("registry root signatures missing")

    if errors:
        for item in errors:
            print(item)
        return 1

    print("FogStack filesystem registry root passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
