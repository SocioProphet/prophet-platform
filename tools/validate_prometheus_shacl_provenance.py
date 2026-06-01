#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts" / "ontology" / "prometheus-sr-assertion-compat.manifest.json"
SHACL_PATH = ROOT / "contracts" / "ontology" / "sr-assertion.shacl.ttl"
SOURCE_PATH = "shapes/symbolic-regression/sr-assertion.shacl.ttl"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return data


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def find_shape_source(manifest: dict[str, Any]) -> dict[str, Any]:
    for item in manifest.get("pinnedSources", []):
        if item.get("repo") == "SocioProphet/ontogenesis" and item.get("path") == SOURCE_PATH:
            return item
    raise SystemExit("manifest missing pinned Ontogenesis SHACL source")


def validate_terms(content: str, terms: list[Any]) -> None:
    missing = [str(term) for term in terms if str(term) not in content]
    if missing:
        raise SystemExit(f"vendored SHACL missing manifest terms: {missing}")


def main() -> int:
    manifest = load_json(MANIFEST)
    source = find_shape_source(manifest)
    expected = source.get("blobSha")
    actual = git_blob_sha(SHACL_PATH)
    if expected != actual:
        raise SystemExit(f"vendored SHACL blob SHA mismatch: expected {expected}, got {actual}")
    validate_terms(SHACL_PATH.read_text(encoding="utf-8"), source.get("requiredTerms", []))
    print(json.dumps({"valid": True, "path": str(SHACL_PATH), "blobSha": actual}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
