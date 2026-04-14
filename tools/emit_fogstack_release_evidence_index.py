#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a Fog Stack release evidence index")
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest-ref", required=True)
    parser.add_argument("--validation-record-ref", required=True)
    parser.add_argument("--signature-verification-record-ref", required=True)
    parser.add_argument("--signature-trust-record-ref", required=True)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    record = {
        "kind": "FogStackReleaseEvidenceIndex",
        "schema_version": "v0.1",
        "bundle_id": args.bundle_id,
        "version": args.version,
        "manifest_ref": args.manifest_ref,
        "validation_record_ref": args.validation_record_ref,
        "signature_verification_record_ref": args.signature_verification_record_ref,
        "signature_trust_record_ref": args.signature_trust_record_ref,
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
