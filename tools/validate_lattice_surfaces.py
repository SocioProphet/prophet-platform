#!/usr/bin/env python3
"""Validate Prophet Lattice product-surface contract examples.

This platform gate verifies that the platform can ingest the current handoff
objects from `sourceos-boot` and `lattice-forge` without depending on those repos
at runtime.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SHA256_RE = re.compile(r"^sha256:[a-fA-F0-9]{64}$")
HEX64_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"{path} must contain a JSON object")
    return data


def require_keys(obj: dict, keys: list[str], where: str) -> None:
    missing = [key for key in keys if key not in obj]
    require(not missing, f"{where} missing keys: {', '.join(missing)}")


def validate_boot_release_set(path: Path) -> None:
    doc = load(path)
    require(doc.get("apiVersion") == "sourceos.dev/v1", "BootReleaseSet apiVersion must be sourceos.dev/v1")
    require(doc.get("kind") == "BootReleaseSet", "BootReleaseSet kind mismatch")
    require_keys(doc, ["metadata", "spec"], "BootReleaseSet")
    spec = doc["spec"]
    require_keys(spec, ["platforms", "channels", "artifacts", "policy", "evidence", "provenance", "trust", "signature", "antiRollback", "telemetry"], "BootReleaseSet.spec")
    require(spec["artifacts"], "BootReleaseSet must have artifacts")
    for artifact in spec["artifacts"]:
        require_keys(artifact, ["name", "role", "uri", "sha256"], "BootReleaseSet artifact")
        require(HEX64_RE.match(artifact["sha256"]) is not None, "BootReleaseSet artifact sha256 must be 64 hex characters")
    require(SHA256_RE.match(spec["signature"]["digest"]) is not None, "BootReleaseSet signature.digest must be sha256:<64 hex>")


def validate_runtime_asset(path: Path) -> None:
    doc = load(path)
    require(doc.get("apiVersion") == "lattice.socioprophet.dev/v1", "RuntimeAsset apiVersion must be lattice.socioprophet.dev/v1")
    require(doc.get("kind") == "RuntimeAsset", "RuntimeAsset kind mismatch")
    require_keys(doc, ["metadata", "spec"], "RuntimeAsset")
    spec = doc["spec"]
    require_keys(spec, ["runtimeClass", "languages", "build", "artifacts", "provenance", "sbom", "signature", "scan", "policy", "compatibility", "telemetry", "promotion"], "RuntimeAsset.spec")
    require(spec["artifacts"], "RuntimeAsset must have artifacts")
    for artifact in spec["artifacts"]:
        require_keys(artifact, ["name", "role", "digest"], "RuntimeAsset artifact")
        require(SHA256_RE.match(artifact["digest"]) is not None, "RuntimeAsset artifact digest must be sha256:<64 hex>")
    require(SHA256_RE.match(spec["sbom"]["digest"]) is not None, "RuntimeAsset sbom.digest must be sha256:<64 hex>")
    require(SHA256_RE.match(spec["signature"]["digest"]) is not None, "RuntimeAsset signature.digest must be sha256:<64 hex>")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    checks = [
        (validate_boot_release_set, root / "contracts" / "lattice" / "boot-release-set.v1.example.json"),
        (validate_runtime_asset, root / "contracts" / "lattice" / "runtime-asset.v1.example.json"),
    ]
    failed = False
    for validator, path in checks:
        try:
            validator(path)
            print(f"PASS {path}")
        except Exception as exc:  # noqa: BLE001
            failed = True
            print(f"FAIL {path}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
