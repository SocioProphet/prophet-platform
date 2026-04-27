#!/usr/bin/env python3
"""CLI for notebook surface adapter launch dry-runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .notebook_launch import demo_launch_plans, launch_plan_evidence, launch_plan_set_to_platform_record


def emit_demo_launch_plans(args: argparse.Namespace) -> int:
    plans = demo_launch_plans()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    plans_path = args.output_dir / "notebook-launch-plans.json"
    evidence_path = args.output_dir / "notebook-launch-evidence.json"
    record_path = args.output_dir / "notebook-launch-platform-record.json"

    plans_path.write_text(
        json.dumps(
            {
                "apiVersion": "studio.socioprophet.dev/v1",
                "kind": "NotebookSurfaceLaunchPlanSet",
                "plans": [plan.to_dict() for plan in plans],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    evidence_path.write_text(json.dumps(launch_plan_evidence(plans), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(
        json.dumps(launch_plan_set_to_platform_record(plans), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"written": [str(plans_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio notebook adapter launch dry-runs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo_parser = subparsers.add_parser("emit-demo", help="Emit demo launch plans for all notebook adapters")
    demo_parser.add_argument("--output-dir", type=Path, required=True)
    demo_parser.set_defaults(func=emit_demo_launch_plans)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-notebook-launch: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
