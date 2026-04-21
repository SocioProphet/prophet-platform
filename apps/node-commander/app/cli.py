from __future__ import annotations

import argparse
import json
from typing import Sequence

import uvicorn

from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="node-commander")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the node-commander runtime HTTP service")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)

    sub.add_parser("print-config", help="print the effective loaded config")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "print-config":
        print(json.dumps(load_config(), indent=2, sort_keys=True))
        return 0

    if args.command == "serve":
        uvicorn.run("app.runtime_main:app", host=args.host, port=args.port)
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
