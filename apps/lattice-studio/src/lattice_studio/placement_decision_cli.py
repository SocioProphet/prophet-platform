#!/usr/bin/env python3
"""CLI for Lattice Studio placement dry-run reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .placement_decision import (
    demo_placement_dry_run_report,
    placement_dry_run_evidence,
    placement_dry_run_to_platform_record,
)


def emit_demo(args: argparse.Namespace) -> int:
    report = demo_placement_dry_run_report()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "placement-dry-run-report.json"
    evidence_path = args.output_dir / "placement-dry-run-evidence.json"
    record_path = args.output_dir / "placement-dry-run-platform-record.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(placement_dry_run_evidence(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(placement_dry_run_to_platform_record(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(report_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio placement dry-run report")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("emit-demo", help="Emit demo placement dry-run report")
    demo.add_argument("--output-dir", type=Path, required=True)
    demo.set_defaults(func=emit_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-placement-decision: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
