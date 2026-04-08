from __future__ import annotations

import argparse
import importlib
import json

from .catalog import read_entries
from .ingest import ingest_path
from .receipts import make_bundle, write_bundle


def _import_upstream():
    try:
        return importlib.import_module("lampstand.cli")
    except Exception as exc:
        raise RuntimeError(
            "Upstream Lampstand is not vendored or installed. "
            "Import it under apps/lampstand/vendor/lampstand-src or install it into the environment."
        ) from exc


def cmd_doctor(_: argparse.Namespace) -> int:
    status = {"ok": True, "upstream_importable": False}
    try:
        _import_upstream()
        status["upstream_importable"] = True
    except Exception as exc:
        status["ok"] = False
        status["error"] = str(exc)
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if status["ok"] else 2


def cmd_emit_receipt(args: argparse.Namespace) -> int:
    bundle = make_bundle(
        event_type=args.event_type,
        action=args.action,
        status=args.status,
        subject_ref=args.subject_ref,
        payload_ref=args.payload_ref,
        metrics={"note": args.note} if args.note else {},
    )
    event_path, receipt_path = write_bundle(bundle)
    print(json.dumps({
        "ok": True,
        "event_path": str(event_path),
        "receipt_path": str(receipt_path),
    }, indent=2, sort_keys=True))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    result = ingest_path(
        file_path=args.path,
        scope_ref=args.scope_ref,
        service_ref=args.service_ref,
        classifiers=list(args.classifier or []),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    items = read_entries(limit=args.limit, event_type_prefix=args.event_type_prefix)
    print(json.dumps({"ok": True, "count": len(items), "items": items}, indent=2, sort_keys=True))
    return 0


def _proxy_to_upstream(argv: list[str]) -> int:
    mod = _import_upstream()
    fn = getattr(mod, "main", None)
    if fn is None:
        raise RuntimeError("upstream lampstand.cli does not expose main()")
    return int(fn(argv))


def cmd_proxy(args: argparse.Namespace) -> int:
    upstream_args = list(args.upstream_args or [])
    return _proxy_to_upstream(upstream_args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pp-lampstand", description="Platform wrapper for Lampstand")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_doc = sub.add_parser("doctor", help="Check upstream Lampstand importability")
    p_doc.set_defaults(fn=cmd_doctor)

    p_emit = sub.add_parser("emit-receipt", help="Emit a sample event + receipt bundle")
    p_emit.add_argument("--event-type", default="lampstand.health")
    p_emit.add_argument("--action", default="Health")
    p_emit.add_argument("--status", default="succeeded")
    p_emit.add_argument("--subject-ref", default="service://lampstand")
    p_emit.add_argument("--payload-ref", default="artifact://none")
    p_emit.add_argument("--note")
    p_emit.set_defaults(fn=cmd_emit_receipt)

    p_ingest = sub.add_parser("ingest", help="Ingest a local file into the platform receipt path")
    p_ingest.add_argument("--path", required=True)
    p_ingest.add_argument("--scope-ref", default="scope://local/default")
    p_ingest.add_argument("--service-ref", default="apps/lampstand")
    p_ingest.add_argument("--classifier", action="append")
    p_ingest.set_defaults(fn=cmd_ingest)

    p_discover = sub.add_parser("discover", help="Read back the local receipt catalog")
    p_discover.add_argument("--limit", type=int, default=20)
    p_discover.add_argument("--event-type-prefix")
    p_discover.set_defaults(fn=cmd_discover)

    p_proxy = sub.add_parser("upstream", help="Proxy directly to upstream lampstand CLI")
    p_proxy.add_argument("upstream_args", nargs=argparse.REMAINDER)
    p_proxy.set_defaults(fn=cmd_proxy)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
