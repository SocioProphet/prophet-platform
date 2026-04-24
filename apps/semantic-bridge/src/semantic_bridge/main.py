from __future__ import annotations

import argparse
import json
from pathlib import Path

from .validators import (
    validate_event_envelope,
    validate_membrane_decision,
    validate_zone_publication_outcome,
    validate_zone_publication_plan,
    validate_zone_publication_record,
    validate_zone_publication_request,
)


def cmd_validate(args):
    payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
    if args.kind == "event-envelope":
        result = validate_event_envelope(payload)
    elif args.kind == "membrane-decision":
        result = validate_membrane_decision(payload)
    elif args.kind == "zone-publication-request":
        result = validate_zone_publication_request(payload)
    elif args.kind == "zone-publication-plan":
        result = validate_zone_publication_plan(payload)
    elif args.kind == "zone-publication-record":
        result = validate_zone_publication_record(payload)
    else:
        result = validate_zone_publication_outcome(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


def build_parser():
    parser = argparse.ArgumentParser(prog="pp-semantic-bridge")
    sub = parser.add_subparsers(dest="cmd", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument(
        "--kind",
        required=True,
        choices=[
            "event-envelope",
            "membrane-decision",
            "zone-publication-request",
            "zone-publication-plan",
            "zone-publication-record",
            "zone-publication-outcome",
        ],
    )
    validate.add_argument("--path", required=True)
    validate.set_defaults(fn=cmd_validate)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
