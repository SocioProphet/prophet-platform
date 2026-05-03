#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return value


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
        errors.append("root kind mismatch")
    if not root.get("registry_uri"):
        errors.append("registry_uri missing")

    for release in root.get("releases") or []:
        for ref_key, digest_key in [
            ("release_pointer_ref", "release_pointer_digest"),
            ("registry_publication_index_ref", "registry_publication_index_digest"),
        ]:
            ref = release.get(ref_key) if isinstance(release, dict) else None
            expected = release.get(digest_key) if isinstance(release, dict) else None
            if not isinstance(ref, str) or not Path(ref).exists():
                errors.append(f"missing ref: {ref}")
                continue
            if sha256_file(Path(ref)) != expected:
                errors.append(f"digest mismatch: {ref}")

    ref = root.get("revocation_index_ref")
    expected = root.get("revocation_index_digest")
    if isinstance(ref, str):
        if not Path(ref).exists():
            errors.append(f"missing index: {ref}")
        elif sha256_file(Path(ref)) != expected:
            errors.append("index digest mismatch")

    if args.require_signed:
        sig = root.get("signature")
        if root.get("signed") is not True:
            errors.append("root not signed")
        if not isinstance(sig, dict) or not sig.get("ref"):
            errors.append("signature metadata missing")

    if errors:
        print("\n".join(errors))
        return 1
    print("FogStack registry root metadata passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
