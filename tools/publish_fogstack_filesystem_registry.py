#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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


def safe_name(ref: str) -> str:
    name = Path(ref).name
    if not name or name in {".", ".."}:
        raise SystemExit(f"ERR: unsafe artifact ref: {ref}")
    return name


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a Fog Stack registry publication index to a filesystem registry")
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    index = load_json(args.index)
    if index.get("kind") != "FogStackRegistryPublicationIndex":
        raise SystemExit("ERR: registry publication index kind mismatch")

    release_root = args.registry_root / args.bundle_id / args.version
    artifacts_root = release_root / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)

    for artifact in index.get("artifacts") or []:
        if not isinstance(artifact, dict):
            raise SystemExit("ERR: artifact entry is not an object")
        ref = artifact.get("ref")
        digest = artifact.get("digest")
        if not isinstance(ref, str):
            raise SystemExit("ERR: artifact ref missing")
        source = Path(ref)
        if not source.exists():
            raise SystemExit(f"ERR: artifact source missing: {source}")
        actual_digest = sha256_file(source)
        if actual_digest != digest:
            raise SystemExit(f"ERR: artifact digest mismatch: {source}")
        shutil.copy2(source, artifacts_root / safe_name(ref))

    index_target = release_root / "registry-publication.index.json"
    shutil.copy2(args.index, index_target)

    pointer = {
        "kind": "FogStackFilesystemRegistryReleasePointer",
        "schema_version": "v0.1",
        "bundle_id": args.bundle_id,
        "version": args.version,
        "index_ref": str(index_target),
        "index_digest": sha256_file(index_target),
    }
    (release_root / "release-pointer.json").write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(pointer, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
