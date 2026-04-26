#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Fog Stack promotion approval signature with OpenSSL")
    parser.add_argument("--approval-record", required=True, type=Path)
    parser.add_argument("--signature", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--key-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    proc = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-verify",
            str(args.public_key),
            "-signature",
            str(args.signature),
            str(args.approval_record),
        ],
        capture_output=True,
        text=True,
    )
    passed = proc.returncode == 0
    result = {
        "kind": "FogStackManifestPromotionApprovalSignatureVerification",
        "schema_version": "v0.1",
        "approval_record_ref": str(args.approval_record),
        "approval_record_digest": sha256_file(args.approval_record),
        "signature_ref": str(args.signature),
        "verification_tool": "openssl",
        "key_ref": args.key_ref or str(args.public_key),
        "status": "pass" if passed else "fail",
        "message": proc.stdout.strip() or proc.stderr.strip() or None,
    }
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
