#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
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


def discover_release(registry_root: Path, release_root: Path) -> dict[str, Any]:
    pointer_path = release_root / "release-pointer.json"
    index_path = release_root / "registry-publication.index.json"
    if not pointer_path.exists():
        raise SystemExit(f"ERR: release pointer missing: {pointer_path}")
    if not index_path.exists():
        raise SystemExit(f"ERR: registry publication index missing: {index_path}")
    pointer = load_json(pointer_path)
    bundle_id = pointer.get("bundle_id")
    version = pointer.get("version")
    if not isinstance(bundle_id, str) or not isinstance(version, str):
        raise SystemExit(f"ERR: malformed release pointer identity: {pointer_path}")
    if pointer.get("index_digest") != sha256_file(index_path):
        raise SystemExit(f"ERR: release index digest mismatch: {index_path}")
    return {
        "bundle_id": bundle_id,
        "version": version,
        "pointer_ref": str(pointer_path.relative_to(registry_root)),
        "pointer_digest": sha256_file(pointer_path),
        "index_ref": str(index_path.relative_to(registry_root)),
        "index_digest": sha256_file(index_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a signed-shape Fog Stack filesystem registry root")
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--registry-uri", required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--key-id", default="shape-only-registry-root-key")
    parser.add_argument("--signature-ref", default="shape-only://fogstack/filesystem-registry-root")
    args = parser.parse_args()

    if not args.registry_root.exists():
        raise SystemExit(f"ERR: registry root missing: {args.registry_root}")

    releases: list[dict[str, Any]] = []
    for pointer_path in sorted(args.registry_root.glob("fogstack.*/*/release-pointer.json")):
        releases.append(discover_release(args.registry_root, pointer_path.parent))
    if not releases:
        raise SystemExit("ERR: no Fog Stack filesystem registry releases found")

    unsigned_root: dict[str, Any] = {
        "kind": "FogStackFilesystemRegistryRoot",
        "schema_version": "v0.1",
        "registry_uri": args.registry_uri,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "releases": releases,
        "signatures": [
            {
                "key_id": args.key_id,
                "algorithm": "shape-only",
                "signature_ref": args.signature_ref,
            }
        ],
    }
    digest_material = dict(unsigned_root)
    digest_material["root_digest"] = None
    unsigned_root["root_digest"] = canonical_digest(digest_material)

    output = args.output or (args.registry_root / "registry-root.json")
    output.write_text(json.dumps(unsigned_root, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(unsigned_root, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
