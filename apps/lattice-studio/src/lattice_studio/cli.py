#!/usr/bin/env python3
"""CLI for Lattice Studio governed notebook sessions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .session import create_session, load_json, write_session_bundle


def create_notebook_session(args: argparse.Namespace) -> int:
    runtime_asset = load_json(args.runtime_asset)
    catalog_inputs = args.catalog_input or []
    session = create_session(
        project_id=args.project_id,
        user_id=args.user_id,
        runtime_asset=runtime_asset,
        catalog_inputs=catalog_inputs,
        policy_ref=args.policy_ref,
    )
    written = write_session_bundle(session, args.output_dir)
    print(json.dumps({"written": [str(path) for path in written]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio governed notebook sessions")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-session", help="Create a governed NotebookSession bundle")
    create_parser.add_argument("--project-id", required=True)
    create_parser.add_argument("--user-id", required=True)
    create_parser.add_argument("--runtime-asset", type=Path, required=True)
    create_parser.add_argument("--catalog-input", action="append", default=[])
    create_parser.add_argument("--policy-ref")
    create_parser.add_argument("--output-dir", type=Path, required=True)
    create_parser.set_defaults(func=create_notebook_session)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-studio: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
