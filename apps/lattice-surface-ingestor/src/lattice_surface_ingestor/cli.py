#!/usr/bin/env python3
"""Command-line interface for Lattice surface ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .ingest import ingest_surface


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def ingest(args: argparse.Namespace) -> int:
    records = [ingest_surface(load_json(path)).to_dict() for path in args.inputs]
    payload: dict[str, Any] = {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecordSet",
        "records": records,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Lattice product-surface handoff objects")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="Normalize handoff objects into PlatformAssetRecordSet")
    ingest_parser.add_argument("inputs", type=Path, nargs="+")
    ingest_parser.set_defaults(func=ingest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-surface-ingest: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
