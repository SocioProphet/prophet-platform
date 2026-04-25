#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a publishable Fog Stack manifest set")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", action="append", required=True, type=Path)
    parser.add_argument("--signature-type", choices=["cosign", "sigstore", "other"], default=None)
    parser.add_argument("--signature-ref-prefix", default=None)
    args = parser.parse_args()

    manifests_dir = args.output_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    publication_index: dict[str, Any] = {
        "kind": "FogStackManifestPublicationSet",
        "schema_version": "v0.1",
        "manifests": [],
    }

    for manifest_path in args.manifest:
        data = load_json(manifest_path)
        if args.signature_type and args.signature_ref_prefix:
            bundle_id = data.get("bundle_id")
            version = data.get("version")
            data["signed"] = True
            data["signature"] = {
                "type": args.signature_type,
                "ref": f"{args.signature_ref_prefix.rstrip('/')}/{bundle_id}-{version}.sig",
            }

        out_path = manifests_dir / manifest_path.name
        out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        publication_index["manifests"].append(
            {
                "bundle_id": data.get("bundle_id"),
                "version": data.get("version"),
                "ref": str(out_path),
                "signed": data.get("signed"),
            }
        )

    index_path = args.output_dir / "manifest-publication-set.json"
    index_path.write_text(json.dumps(publication_index, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
