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


def build_record_set(inputs: list[Path]) -> dict[str, Any]:
    records = [ingest_surface(load_json(path)).to_dict() for path in inputs]
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecordSet",
        "records": records,
    }


def emit_payload(payload: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def ingest(args: argparse.Namespace) -> int:
    payload = build_record_set(args.inputs)
    emit_payload(payload, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Lattice product-surface handoff objects")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="Normalize handoff objects into PlatformAssetRecordSet")
    ingest_parser.add_argument("inputs", type=Path, nargs="+")
    ingest_parser.add_argument("--output", type=Path, help="Optional path for deterministic JSON output")
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
