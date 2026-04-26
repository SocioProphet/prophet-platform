#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def parse_approval(value: str) -> dict[str, str | None]:
    parts = value.split(":", 2)
    if len(parts) < 2:
        raise SystemExit("ERR: approvals must be approver:role[:statement]")
    approver, role = parts[0], parts[1]
    statement = parts[2] if len(parts) == 3 else None
    return {"approver": approver, "role": role, "statement": statement}


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a Fog Stack manifest promotion approval record")
    parser.add_argument("--promotion-set", required=True, type=Path)
    parser.add_argument("--required-approvals", required=True, type=int)
    parser.add_argument("--approval", action="append", required=True, help="approver:role[:statement]")
    parser.add_argument("--status", default="approved", choices=["approved", "rejected", "shape-only"])
    parser.add_argument("--signature-type", choices=["cosign", "sigstore", "other"], default=None)
    parser.add_argument("--signature-ref", default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    promotion = load_json(args.promotion_set)
    promotion_meta = promotion.get("promotion") or {}

    signature = None
    signed = False
    if args.signature_type or args.signature_ref:
        if not args.signature_type or not args.signature_ref:
            raise SystemExit("ERR: both --signature-type and --signature-ref are required for signed approvals")
        signature = {"type": args.signature_type, "ref": args.signature_ref}
        signed = True

    record = {
        "kind": "FogStackManifestPromotionApprovalRecord",
        "schema_version": "v0.1",
        "promotion_set_ref": str(args.promotion_set),
        "promotion_set_digest": sha256_file(args.promotion_set),
        "target_channel": promotion_meta.get("channel"),
        "target_support_state": promotion_meta.get("support_state"),
        "status": args.status,
        "required_approvals": args.required_approvals,
        "approvals": [parse_approval(item) for item in args.approval],
        "signed": signed,
        "signature": signature,
        "notes": args.notes,
    }

    text = json.dumps(record, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
