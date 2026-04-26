#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def main() -> int:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proof_dir = tmp_path / "proof"
        registry_root = tmp_path / "registry"

        subprocess.run([
            sys.executable,
            str(ROOT / "tools" / "build_sourceos_m2_lifecycle_proof.py"),
            "--output-dir",
            str(proof_dir),
        ], check=True)

        subprocess.run([
            sys.executable,
            str(ROOT / "tools" / "publish_sourceos_m2_filesystem_registry.py"),
            "--proof-dir",
            str(proof_dir),
            "--registry-root",
            str(registry_root),
            "--release-id",
            "srset-m2-demo-0001",
            "--version",
            "0.0.1-demo",
        ], check=True)

        release_root = registry_root / "sourceos" / "srset-m2-demo-0001" / "0.0.1-demo"
        pointer_path = release_root / "release-pointer.json"
        proof_index_path = release_root / "proof-index.json"
        if not pointer_path.exists():
            raise SystemExit("ERR: missing release-pointer.json")
        if not proof_index_path.exists():
            raise SystemExit("ERR: missing proof-index.json")

        pointer = load(pointer_path)
        if pointer.get("kind") != "SourceOSFilesystemRegistryReleasePointer":
            raise SystemExit("ERR: release pointer kind mismatch")
        artifact_paths = {item.get("path") for item in pointer.get("artifacts", [])}
        required = {
            "artifacts/config-source.json",
            "artifacts/release-set.json",
            "artifacts/boot-release-set.json",
            "artifacts/nlboot-crosswalk.json",
            "artifacts/fingerprint.json",
            "artifacts/compliance-result.json",
        }
        missing = sorted(required - artifact_paths)
        if missing:
            raise SystemExit("ERR: registry pointer missing artifacts: " + ", ".join(missing))

    print("SourceOS M2 filesystem registry smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
