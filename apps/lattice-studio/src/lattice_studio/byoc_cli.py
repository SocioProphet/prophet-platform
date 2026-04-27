#!/usr/bin/env python3
"""CLI for BYOC placement dry-runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .byoc import byoc_evidence, byoc_to_platform_record, demo_byoc_placement_plan


def emit_demo(args: argparse.Namespace) -> int:
    plan = demo_byoc_placement_plan()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.output_dir / "byoc-placement-plan.json"
    evidence_path = args.output_dir / "byoc-placement-evidence.json"
    record_path = args.output_dir / "byoc-platform-record.json"
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(byoc_evidence(plan), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(byoc_to_platform_record(plan), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(plan_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio BYOC placement dry-run")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("emit-demo", help="Emit demo BYOC storage/compute/I/O placement plan")
    demo.add_argument("--output-dir", type=Path, required=True)
    demo.set_defaults(func=emit_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-byoc: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
