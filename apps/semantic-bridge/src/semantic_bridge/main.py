from __future__ import annotations

import argparse
import json
from pathlib import Path

from .validators import validate_event_envelope, validate_membrane_decision


def cmd_validate(args):
    payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
    if args.kind == "event-envelope":
        result = validate_event_envelope(payload)
    else:
        result = validate_membrane_decision(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


def build_parser():
    parser = argparse.ArgumentParser(prog="pp-semantic-bridge")
    sub = parser.add_subparsers(dest="cmd", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--kind", required=True, choices=["event-envelope", "membrane-decision"])
    validate.add_argument("--path", required=True)
    validate.set_defaults(fn=cmd_validate)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
