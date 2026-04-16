#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Liberty Stack manifest shape")
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    required_top = ["manifest_id", "owner_ref", "datasets"]
    missing = [k for k in required_top if k not in payload]
    if missing:
        print(json.dumps({"ok": False, "missing": missing}))
        return 2

    if not isinstance(payload.get("datasets"), list) or not payload["datasets"]:
        print(json.dumps({"ok": False, "error": "datasets must be a non-empty list"}))
        return 2

    first = payload["datasets"][0]
    dataset_required = ["dataset_id", "provider", "service", "target_format", "verification_method"]
    dataset_missing = [k for k in dataset_required if k not in first]
    if dataset_missing:
        print(json.dumps({"ok": False, "dataset_missing": dataset_missing}))
        return 2

    print(json.dumps({"ok": True, "manifest_id": payload["manifest_id"], "datasets": len(payload["datasets"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
