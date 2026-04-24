#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize external signature verification output into FogStackExternalSignatureVerificationEvidence")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--tool", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))

    # minimal normalization contract
    evidence = {
        "kind": "FogStackExternalSignatureVerificationEvidence",
        "schema_version": "v0.1",
        "tool": args.tool,
        "status": raw.get("status") or "unknown",
        "message": raw.get("message"),
        "verified_digest": raw.get("verified_digest"),
        "evidence_count": raw.get("evidence_count"),
        "key_ref": raw.get("key_ref"),
        "raw_ref": str(args.input),
    }

    text = json.dumps(evidence, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
