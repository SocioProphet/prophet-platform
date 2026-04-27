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
    parser = argparse.ArgumentParser(description="Check Fog Stack registry root metadata")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--require-signed", action="store_true")
    args = parser.parse_args()

    root = load_json(args.root)
    errors: list[str] = []

    if root.get("kind") != "FogStackRegistryRootMetadata":
        errors.append("registry root kind mismatch")
    if not root.get("registry_uri"):
        errors.append("registry_uri is required")

    for release in root.get("releases") or []:
        if not isinstance(release, dict):
            errors.append("release entry is not an object")
            continue
        pointer_ref = release.get("release_pointer_ref")
        pointer_digest = release.get("release_pointer_digest")
        index_ref = release.get("registry_publication_index_ref")
        index_digest = release.get("registry_publication_index_digest")
        for label, ref, digest in (
            ("release pointer", pointer_ref, pointer_digest),
            ("registry publication index", index_ref, index_digest),
        ):
            if not isinstance(ref, str) or not Path(ref).exists():
                errors.append(f"{label} missing: {ref}")
                continue
            if sha256_file(Path(ref)) != digest:
                errors.append(f"{label} digest mismatch: {ref}")

    rev_ref = root.get("revocation_index_ref")
    rev_digest = root.get("revocation_index_digest")
    if isinstance(rev_ref, str):
        if not Path(rev_ref).exists():
            errors.append(f"revocation index missing: {rev_ref}")
        elif sha256_file(Path(rev_ref)) != rev_digest:
            errors.append("revocation index digest mismatch")

    if args.require_signed:
        if root.get("signed") is not True:
            errors.append("registry root is not marked signed")
        signature = root.get("signature")
        if not isinstance(signature, dict):
            errors.append("signed registry root missing signature object")
        else:
            if signature.get("type") not in {"cosign", "sigstore", "other"}:
                errors.append("invalid registry root signature type")
            if not isinstance(signature.get("ref"), str) or not signature.get("ref"):
                errors.append("registry root signature ref missing")

    if errors:
        for item in errors:
            print(item)
        return 1

    print("FogStack registry root metadata passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
