#!/usr/bin/env python3
"""CLI for notebook promotion compiler dry-runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .notebook_promotion import demo_notebook_promotion_bundle, promotion_evidence, promotion_to_platform_record


def emit_demo(args: argparse.Namespace) -> int:
    bundle = demo_notebook_promotion_bundle()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = args.output_dir / "notebook-promotion-bundle.json"
    evidence_path = args.output_dir / "notebook-promotion-evidence.json"
    record_path = args.output_dir / "notebook-promotion-platform-record.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(promotion_evidence(bundle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(promotion_to_platform_record(bundle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(bundle_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio notebook promotion compiler")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("emit-demo", help="Emit demo notebook promotion bundle")
    demo.add_argument("--output-dir", type=Path, required=True)
    demo.set_defaults(func=emit_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-notebook-promotion: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
