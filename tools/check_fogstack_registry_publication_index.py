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
    parser = argparse.ArgumentParser(description="Check a Fog Stack registry publication index")
    parser.add_argument("--index", required=True, type=Path)
    args = parser.parse_args()

    index = load_json(args.index)
    errors = []

    if index.get("kind") != "FogStackRegistryPublicationIndex":
        errors.append("index kind mismatch")
    if not index.get("registry_uri"):
        errors.append("registry_uri is required")

    pub_ref = index.get("publication_set_ref")
    pub_digest = index.get("publication_set_digest")
    if isinstance(pub_ref, str) and Path(pub_ref).exists():
        if sha256_file(Path(pub_ref)) != pub_digest:
            errors.append("publication set digest mismatch")
    else:
        errors.append("publication_set_ref missing or not found")

    gate_ref = index.get("publication_gate_record_ref")
    gate_digest = index.get("publication_gate_record_digest")
    if isinstance(gate_ref, str) and Path(gate_ref).exists():
        gate = load_json(Path(gate_ref))
        if gate.get("status") != "pass":
            errors.append("publication gate status is not pass")
        if sha256_file(Path(gate_ref)) != gate_digest:
            errors.append("publication gate record digest mismatch")
    else:
        errors.append("publication_gate_record_ref missing or not found")

    artifacts = index.get("artifacts") or []
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts list is missing or empty")
    else:
        for artifact in artifacts:
            ref = artifact.get("ref") if isinstance(artifact, dict) else None
            digest = artifact.get("digest") if isinstance(artifact, dict) else None
            if not isinstance(ref, str) or not Path(ref).exists():
                errors.append(f"artifact ref missing or not found: {ref}")
                continue
            if sha256_file(Path(ref)) != digest:
                errors.append(f"artifact digest mismatch: {ref}")

    if errors:
        for item in errors:
            print(item)
        return 1

    print("FogStack registry publication index passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
