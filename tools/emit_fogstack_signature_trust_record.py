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
    parser = argparse.ArgumentParser(description="Emit a Fog Stack signature trust record from external verification evidence")
    parser.add_argument("--verification-evidence", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest-ref", required=True)
    parser.add_argument("--signature-ref", required=True)
    parser.add_argument("--verification-method", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--validation-record-ref", default=None)
    parser.add_argument("--signature-verification-record-ref", default=None)
    parser.add_argument("--key-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    evidence = load_json(args.verification_evidence)
    status = evidence.get("status")
    if status == "pass":
        trust_status = "verified"
    elif status == "fail":
        trust_status = "failed"
    else:
        trust_status = "shape-only"

    record = {
        "kind": "FogStackSignatureTrustRecord",
        "schema_version": "v0.1",
        "bundle_id": args.bundle_id,
        "version": args.version,
        "manifest_ref": args.manifest_ref,
        "signature_ref": args.signature_ref,
        "verification_method": args.verification_method,
        "status": trust_status,
        "summary": {
            "status": status,
            "message": evidence.get("message"),
            "evidence_count": evidence.get("evidence_count"),
        },
        "validation_record_ref": args.validation_record_ref,
        "signature_verification_record_ref": args.signature_verification_record_ref,
        "key_ref": args.key_ref,
    }

    text = json.dumps(record, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
