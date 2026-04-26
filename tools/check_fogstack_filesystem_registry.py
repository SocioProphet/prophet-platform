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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a Fog Stack filesystem registry release")
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    release_root = args.registry_root / args.bundle_id / args.version
    pointer_path = release_root / "release-pointer.json"
    index_path = release_root / "registry-publication.index.json"

    errors: list[str] = []
    if not pointer_path.exists():
        errors.append("release-pointer.json missing")
    if not index_path.exists():
        errors.append("registry-publication.index.json missing")

    if errors:
        for item in errors:
            print(item)
        return 1

    pointer = load_json(pointer_path)
    index = load_json(index_path)

    if pointer.get("index_digest") != sha256_file(index_path):
        errors.append("index digest mismatch")
    if pointer.get("bundle_id") != args.bundle_id or pointer.get("version") != args.version:
        errors.append("release pointer identity mismatch")

    artifacts_root = release_root / "artifacts"
    for artifact in index.get("artifacts") or []:
        ref = artifact.get("ref") if isinstance(artifact, dict) else None
        digest = artifact.get("digest") if isinstance(artifact, dict) else None
        if not isinstance(ref, str):
            errors.append("artifact ref missing")
            continue
        artifact_path = artifacts_root / Path(ref).name
        if not artifact_path.exists():
            errors.append(f"artifact missing: {artifact_path}")
            continue
        if sha256_file(artifact_path) != digest:
            errors.append(f"artifact digest mismatch: {artifact_path}")

    if errors:
        for item in errors:
            print(item)
        return 1

    print("FogStack filesystem registry release passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
