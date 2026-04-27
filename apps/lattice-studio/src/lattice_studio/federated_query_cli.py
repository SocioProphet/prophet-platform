#!/usr/bin/env python3
"""CLI for Lattice Studio federated query plane artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .federated_query import (
    demo_federated_query_plane,
    federated_query_evidence,
    federated_query_to_platform_record,
)


def emit_demo(args: argparse.Namespace) -> int:
    plane = demo_federated_query_plane()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plane_path = args.output_dir / "federated-query-plane.json"
    evidence_path = args.output_dir / "federated-query-evidence.json"
    record_path = args.output_dir / "federated-query-platform-record.json"
    plane_path.write_text(json.dumps(plane.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(federated_query_evidence(plane), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(federated_query_to_platform_record(plane), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(plane_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio federated query plane")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("emit-demo", help="Emit demo federated query plane artifacts")
    demo.add_argument("--output-dir", type=Path, required=True)
    demo.set_defaults(func=emit_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-federated-query: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
