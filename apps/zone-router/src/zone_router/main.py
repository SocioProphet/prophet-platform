from __future__ import annotations

import argparse
import json

from .resolver import resolve_topic


def cmd_plan(args):
    topic = resolve_topic(args.zone_ref, args.event_type)
    plan = {
        "ok": True,
        "zone_ref": args.zone_ref,
        "event_type": args.event_type,
        "topic": topic,
        "carrier_ref": args.carrier_ref,
        "event_ref": args.event_ref,
        "receipt_ref": args.receipt_ref,
        "catalog_ref": args.catalog_ref,
    }
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="pp-zone-router")
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--zone-ref", required=True)
    plan.add_argument("--event-type", required=True)
    plan.add_argument("--carrier-ref", required=True)
    plan.add_argument("--event-ref", required=True)
    plan.add_argument("--receipt-ref", required=True)
    plan.add_argument("--catalog-ref", required=True)
    plan.set_defaults(fn=cmd_plan)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
