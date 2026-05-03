#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


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


def path_from_ref(ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else ROOT / path


def validate_index(index_path: Path) -> list[str]:
    index = load_json(index_path)
    errors: list[str] = []

    if index.get("kind") != "FogStackLocalDemoArtifactIndex":
        errors.append("index kind mismatch")
    if index.get("schema_version") != "v0.1":
        errors.append("index schema_version mismatch")

    artifacts = index.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts list missing or empty")
        return errors

    seen_ids: set[str] = set()
    seen_refs: set[str] = set()
    for position, entry in enumerate(artifacts):
        if not isinstance(entry, dict):
            errors.append(f"artifact[{position}] is not an object")
            continue

        artifact_id = entry.get("id")
        artifact_ref = entry.get("ref")
        digest = entry.get("digest")
        size_bytes = entry.get("size_bytes")

        if not isinstance(artifact_id, str) or not artifact_id:
            errors.append(f"artifact[{position}] id missing or malformed")
        elif artifact_id in seen_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        else:
            seen_ids.add(artifact_id)

        if not isinstance(artifact_ref, str) or not artifact_ref:
            errors.append(f"artifact[{position}] ref missing or malformed")
            continue
        if artifact_ref in seen_refs:
            errors.append(f"duplicate artifact ref: {artifact_ref}")
        else:
            seen_refs.add(artifact_ref)

        if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
            errors.append(f"artifact[{position}] digest missing or malformed")

        if not isinstance(size_bytes, int) or size_bytes <= 0:
            errors.append(f"artifact[{position}] size_bytes missing or non-positive")

        artifact_path = path_from_ref(artifact_ref)
        if not artifact_path.exists():
            errors.append(f"artifact missing: {artifact_ref}")
            continue
        if not artifact_path.is_file():
            errors.append(f"artifact is not a file: {artifact_ref}")
            continue

        actual_digest = sha256_file(artifact_path)
        if isinstance(digest, str) and actual_digest != digest:
            errors.append(f"artifact digest mismatch: {artifact_ref}")

        actual_size = artifact_path.stat().st_size
        if isinstance(size_bytes, int) and actual_size != size_bytes:
            errors.append(f"artifact size mismatch: {artifact_ref}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a FogStack local demo artifact digest index")
    parser.add_argument("--index", required=True, type=Path)
    args = parser.parse_args()

    errors = validate_index(args.index)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("FogStack local demo artifact index passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
