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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def safe_copy_name(path: Path) -> str:
    name = path.name
    if not name or name in {".", ".."}:
        raise SystemExit(f"ERR: unsafe artifact name for {path}")
    return name


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a SourceOS M2 proof bundle into a filesystem registry layout")
    parser.add_argument("--proof-dir", required=True, type=Path)
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--release-id", default="srset-m2-demo-0001")
    parser.add_argument("--version", default="0.0.1-demo")
    args = parser.parse_args()

    proof_index_path = args.proof_dir / "proof-index.json"
    proof_index = load_json(proof_index_path)
    if proof_index.get("kind") != "SourceOSProofIndex":
        raise SystemExit("ERR: proof-index kind mismatch")

    release_root = args.registry_root / "sourceos" / args.release_id / args.version
    artifacts_root = release_root / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)

    copied_artifacts: list[dict[str, Any]] = []
    for item in proof_index.get("artifacts") or []:
        if not isinstance(item, dict):
            raise SystemExit("ERR: proof-index artifact entry is not an object")
        rel_path = item.get("path")
        expected_digest = item.get("digest")
        if not isinstance(rel_path, str):
            raise SystemExit("ERR: proof-index artifact path missing")
        source = args.proof_dir / rel_path
        if not source.exists():
            raise SystemExit(f"ERR: proof artifact missing: {source}")
        actual_digest = sha256_file(source)
        if actual_digest != expected_digest:
            raise SystemExit(f"ERR: proof artifact digest mismatch: {source}")
        target = artifacts_root / safe_copy_name(source)
        shutil.copy2(source, target)
        copied_artifacts.append({
            "name": item.get("name"),
            "kind": item.get("kind"),
            "path": f"artifacts/{target.name}",
            "digest": actual_digest,
        })

    proof_index_target = release_root / "proof-index.json"
    shutil.copy2(proof_index_path, proof_index_target)

    pointer = {
        "kind": "SourceOSFilesystemRegistryReleasePointer",
        "schema_version": "sourceos.filesystem-registry-pointer/v0",
        "release_id": args.release_id,
        "version": args.version,
        "proof_index_ref": "proof-index.json",
        "proof_index_digest": sha256_file(proof_index_target),
        "artifacts": copied_artifacts,
    }
    write_json(release_root / "release-pointer.json", pointer)
    print(json.dumps(pointer, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
