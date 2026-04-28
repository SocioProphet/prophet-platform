#!/usr/bin/env python3
"""CLI for Lattice Studio query routing dry-run plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .query_planner import (
    demo_query_routing_dry_run_plan,
    query_routing_evidence,
    query_routing_to_platform_record,
)


def emit_demo(args: argparse.Namespace) -> int:
    plan = demo_query_routing_dry_run_plan()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.output_dir / "query-routing-dry-run-plan.json"
    evidence_path = args.output_dir / "query-routing-evidence.json"
    record_path = args.output_dir / "query-routing-platform-record.json"
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(query_routing_evidence(plan), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(query_routing_to_platform_record(plan), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(plan_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio query routing dry-run planner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("emit-demo", help="Emit demo query routing dry-run artifacts")
    demo.add_argument("--output-dir", type=Path, required=True)
    demo.set_defaults(func=emit_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-query-routing: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
