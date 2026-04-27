#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_entry(value: str) -> dict[str, str | None]:
    parts = value.split(":", 4)
    if len(parts) < 3:
        raise SystemExit("ERR: entries must be bundle_id:version:status[:reason[:superseded_by]]")
    bundle_id, version, status = parts[0], parts[1], parts[2]
    if status not in {"revoked", "rollback"}:
        raise SystemExit("ERR: status must be revoked or rollback")
    reason = parts[3] if len(parts) >= 4 and parts[3] else None
    superseded_by = parts[4] if len(parts) == 5 and parts[4] else None
    return {
        "bundle_id": bundle_id,
        "version": version,
        "status": status,
        "reason": reason,
        "superseded_by": superseded_by,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Fog Stack registry revocation index")
    parser.add_argument("--entry", action="append", default=[], help="bundle_id:version:status[:reason[:superseded_by]]")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    index = {
        "kind": "FogStackRegistryRevocationIndex",
        "schema_version": "v0.1",
        "entries": [parse_entry(item) for item in args.entry],
    }
    text = json.dumps(index, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
