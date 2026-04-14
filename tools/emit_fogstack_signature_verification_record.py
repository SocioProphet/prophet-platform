#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a Fog Stack signature verification record from manifest verification JSON")
    parser.add_argument("--verification-json", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest-ref", required=True)
    parser.add_argument("--signature-ref", default=None)
    parser.add_argument("--validation-record-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    verification = load_json(args.verification_json)
    summary = verification.get("summary") or {}
    if not isinstance(summary, dict):
        raise SystemExit("ERR: verification summary is missing or malformed")

    status = "verified" if summary.get("status") == "pass" else "failed"
    if summary.get("status") == "warn":
        status = "shape-only"

    record = {
        "kind": "FogStackSignatureVerificationRecord",
        "schema_version": "v0.1",
        "bundle_id": args.bundle_id,
        "version": args.version,
        "manifest_ref": args.manifest_ref,
        "status": status,
        "summary": {
            "status": summary.get("status"),
            "exit_code": summary.get("exit_code"),
            "checks_run": summary.get("checks_run"),
        },
        "signature_ref": args.signature_ref,
        "validation_record_ref": args.validation_record_ref,
    }

    text = json.dumps(record, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
