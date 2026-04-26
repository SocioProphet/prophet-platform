#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a Fog Stack manifest publication set")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--support-catalog", required=True, type=Path)
    parser.add_argument("--target-channel", default=None)
    parser.add_argument("--target-support-state", default=None)
    args = parser.parse_args()

    index_path = args.input_dir / "manifest-publication-set.json"
    index = load_json(index_path)
    manifests = index.get("manifests") or []
    if not isinstance(manifests, list):
        raise SystemExit("ERR: publication set manifests list missing or malformed")

    catalog = yaml.safe_load(args.support_catalog.read_text(encoding="utf-8")) or {}
    offerings = catalog.get("offerings") or []
    catalog_map = {
        (item.get("bundle_id"), item.get("version")): item
        for item in offerings
        if isinstance(item, dict)
    }

    out_manifests_dir = args.output_dir / "manifests"
    out_manifests_dir.mkdir(parents=True, exist_ok=True)

    promoted_index: dict[str, Any] = {
        "kind": "FogStackManifestPublicationSet",
        "schema_version": "v0.1",
        "promotion": {
            "channel": args.target_channel,
            "support_state": args.target_support_state,
            "catalog": str(args.support_catalog),
        },
        "manifests": [],
    }

    for item in manifests:
        ref = item.get("ref")
        if not isinstance(ref, str):
            raise SystemExit("ERR: manifest ref missing in publication set")
        src = Path(ref)
        data = load_json(src)
        bundle_id = data.get("bundle_id")
        version = data.get("version")
        cat_item = catalog_map.get((bundle_id, version), {})

        previous_channel = data.get("channel")
        previous_support_state = data.get("support_state")

        target_channel = args.target_channel or cat_item.get("channel") or previous_channel
        target_support_state = args.target_support_state or cat_item.get("support_state") or previous_support_state

        data["channel"] = target_channel
        data["support_state"] = target_support_state

        out_path = out_manifests_dir / src.name
        out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        promoted_index["manifests"].append(
            {
                "bundle_id": bundle_id,
                "version": version,
                "ref": str(out_path),
                "signed": data.get("signed"),
                "previous_channel": previous_channel,
                "previous_support_state": previous_support_state,
                "channel": target_channel,
                "support_state": target_support_state,
                "lifecycle_status": cat_item.get("lifecycle_status"),
            }
        )

    (args.output_dir / "manifest-publication-set.json").write_text(
        json.dumps(promoted_index, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
