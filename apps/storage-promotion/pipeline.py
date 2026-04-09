#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dolt_adapter import insert_observation
from runtime import build_observation, project_promoted, promote_observation
from typedb_adapter import build_insert_tql, persist_tql


def _load_payload(path: str | None) -> dict:
    if not path:
        return {
            "subject": "user123",
            "action": "has_role",
            "object": "admin",
        }
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the storage promotion slice")
    parser.add_argument("--payload-file")
    parser.add_argument("--apply-dolt", action="store_true")
    parser.add_argument("--export-typedb-tql", action="store_true")
    parser.add_argument("--typedb-tql-out")
    parser.add_argument("--dolt-dir")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = _load_payload(args.payload_file)
    observation = build_observation(payload)
    promoted = promote_observation(observation)
    projection = project_promoted(promoted)
    typedb_tql = build_insert_tql(promoted)

    dolt_result = None
    if args.apply_dolt:
        dolt_result = insert_observation(observation, dolt_dir=args.dolt_dir)

    typedb_result = None
    if args.export_typedb_tql:
        typedb_result = persist_tql(typedb_tql, out_path=args.typedb_tql_out)

    print(json.dumps({
        "observation": observation,
        "dolt_result": dolt_result,
        "promoted": promoted,
        "typedb_tql": typedb_tql,
        "typedb_result": typedb_result,
        "projection": projection,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
