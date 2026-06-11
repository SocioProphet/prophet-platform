from __future__ import annotations

import argparse
import json
from pathlib import Path

from .outbox import write_publication_record
from .planner import load_publication_request, plan_publication_request
from .resolver import resolve_topic
from . import semantic_gate as gate


def _fail(name, result):
    print(json.dumps({"ok": False, "check": name, "result": result}, indent=2, sort_keys=True))
    return 2


def cmd_plan(args):
    topic = args.topic_ref or resolve_topic(args.zone_ref, args.event_type)
    plan = {
        "ok": True,
        "zone_ref": args.zone_ref,
        "event_type": args.event_type,
        "topic": topic,
        "publication_mode": "explicit" if args.topic_ref else "resolved",
        "carrier_ref": args.carrier_ref,
        "event_ref": args.event_ref,
        "receipt_ref": args.receipt_ref,
        "catalog_ref": args.catalog_ref,
    }
    if args.topic_ref:
        plan["topic_ref"] = args.topic_ref
    plan_check = gate.validate_plan(plan)
    if not plan_check.get("ok"):
        return _fail("plan", plan_check)
    plan["checks"] = {"plan": plan_check}
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def cmd_plan_request(args):
    request = load_publication_request(args.path)
    request_check = gate.validate_request(request)
    if not request_check.get("ok"):
        return _fail("request", request_check)
    plan = plan_publication_request(request)
    if not plan.get("ok"):
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 2
    plan_check = gate.validate_plan(plan)
    if not plan_check.get("ok"):
        return _fail("plan", plan_check)
    plan["checks"] = {"request": request_check, "plan": plan_check}
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def cmd_enqueue_request(args):
    request = load_publication_request(args.path)
    request_check = gate.validate_request(request)
    if not request_check.get("ok"):
        return _fail("request", request_check)
    plan = plan_publication_request(request)
    if not plan.get("ok"):
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 2
    plan_check = gate.validate_plan(plan)
    if not plan_check.get("ok"):
        return _fail("plan", plan_check)
    result = write_publication_record(plan)
    record_check = gate.validate_record(result["record"])
    result["checks"] = {"request": request_check, "plan": plan_check, "record": record_check}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if record_check.get("ok") else 2


def cmd_enqueue_plan(args):
    plan = json.loads(Path(args.path).read_text(encoding="utf-8"))
    plan_check = gate.validate_plan(plan)
    if not plan_check.get("ok"):
        return _fail("plan", plan_check)
    result = write_publication_record(plan)
    record_check = gate.validate_record(result["record"])
    result["checks"] = {"plan": plan_check, "record": record_check}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if record_check.get("ok") else 2



def cmd_publish_record(args):
    from .transport import load_publication_record, publish_publication_record
    record = load_publication_record(args.path)
    result = publish_publication_record(record, transport_ref=args.transport_ref)
    record_check = gate.validate_record(record)
    result["semantic_validation"] = {"record": record_check}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2

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
    plan.add_argument("--topic-ref")
    plan.set_defaults(fn=cmd_plan)

    plan_request = sub.add_parser("plan-request")
    plan_request.add_argument("--path", required=True)
    plan_request.set_defaults(fn=cmd_plan_request)

    enqueue_request = sub.add_parser("enqueue-request")
    enqueue_request.add_argument("--path", required=True)
    enqueue_request.set_defaults(fn=cmd_enqueue_request)

    enqueue_plan = sub.add_parser("enqueue-plan")
    enqueue_plan.add_argument("--path", required=True)
    enqueue_plan.set_defaults(fn=cmd_enqueue_plan)

    publish_record = sub.add_parser("publish-record")
    publish_record.add_argument("--path", required=True)
    publish_record.add_argument("--transport-ref", default="transport://local/jsonl")
    publish_record.set_defaults(fn=cmd_publish_record)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
