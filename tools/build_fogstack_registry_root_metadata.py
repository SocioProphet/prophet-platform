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
    parser = argparse.ArgumentParser(description="Build Fog Stack registry root metadata")
    parser.add_argument("--registry-uri", required=True)
    parser.add_argument("--release", action="append", nargs=3, metavar=("BUNDLE_ID", "VERSION", "RELEASE_ROOT"), required=True)
    parser.add_argument("--revocation-index", type=Path, default=None)
    parser.add_argument("--signature-type", choices=["cosign", "sigstore", "other"], default=None)
    parser.add_argument("--signature-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    releases = []
    for bundle_id, version, release_root_str in args.release:
        release_root = Path(release_root_str)
        pointer = release_root / "release-pointer.json"
        index = release_root / "registry-publication.index.json"
        if not pointer.exists():
            raise SystemExit(f"ERR: missing release pointer: {pointer}")
        if not index.exists():
            raise SystemExit(f"ERR: missing registry index: {index}")
        releases.append({
            "bundle_id": bundle_id,
            "version": version,
            "release_pointer_ref": str(pointer),
            "release_pointer_digest": sha256_file(pointer),
            "registry_publication_index_ref": str(index),
            "registry_publication_index_digest": sha256_file(index),
        })

    rev_ref = str(args.revocation_index) if args.revocation_index else None
    rev_digest = sha256_file(args.revocation_index) if args.revocation_index else None
    signed = bool(args.signature_type and args.signature_ref)
    root = {
        "kind": "FogStackRegistryRootMetadata",
        "schema_version": "v0.1",
        "registry_uri": args.registry_uri,
        "releases": releases,
        "revocation_index_ref": rev_ref,
        "revocation_index_digest": rev_digest,
        "signed": signed,
        "signature": {"type": args.signature_type, "ref": args.signature_ref} if signed else None,
    }

    text = json.dumps(root, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
