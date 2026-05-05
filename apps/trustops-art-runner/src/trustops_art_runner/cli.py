"""Command line interface for the TrustOps ART runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trustops_art_runner.receipt import TrustOpsRunnerError, build_art_smoke_receipt, write_receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trustops-art-runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a TrustOps ART profile")
    run_parser.add_argument("--profile", default="art-smoke", help="TrustOps profile to run")
    run_parser.add_argument("--manifest", required=True, type=Path, help="Functional service manifest JSON path")
    run_parser.add_argument("--output", required=True, type=Path, help="Output receipt path")
    run_parser.add_argument("--source-commit", default="0000000000000000000000000000000000000000")
    run_parser.add_argument("--created-at", default=None, help="Optional RFC3339 timestamp for deterministic tests")
    run_parser.add_argument("--artifact-ref", default=None, help="Optional durable artifact reference for receipt evidence")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            receipt = build_art_smoke_receipt(
                manifest_path=args.manifest,
                profile=args.profile,
                output_ref=args.artifact_ref,
                source_commit=args.source_commit,
                created_at=args.created_at,
            )
            write_receipt(receipt, args.output)
            print(json.dumps({"status": "ok", "receipt": str(args.output), "receiptId": receipt["receiptId"]}, sort_keys=True))
            return 0
    except TrustOpsRunnerError as exc:
        print(f"trustops-art-runner: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
