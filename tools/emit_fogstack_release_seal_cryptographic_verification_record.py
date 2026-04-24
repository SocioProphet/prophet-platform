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
    parser = argparse.ArgumentParser(description="Emit a Fog Stack release seal cryptographic verification record")
    parser.add_argument("--verification-evidence", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--seal-ref", required=True)
    parser.add_argument("--signature-ref", required=True)
    parser.add_argument("--verification-tool", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--seal-root-hash", default=None)
    parser.add_argument("--key-ref", default=None)
    parser.add_argument("--release-evidence-index-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    evidence = load_json(args.verification_evidence)
    status = evidence.get("status")
    if status == "pass":
        verify_status = "verified"
    elif status == "fail":
        verify_status = "failed"
    else:
        verify_status = "shape-only"

    verified_root_hash = evidence.get("verified_root_hash")
    seal_root_hash_matches = None
    if isinstance(args.seal_root_hash, str) and isinstance(verified_root_hash, str):
        seal_root_hash_matches = args.seal_root_hash == verified_root_hash
        if seal_root_hash_matches is False:
            verify_status = "failed"

    record = {
        "kind": "FogStackReleaseSealCryptographicVerificationRecord",
        "schema_version": "v0.1",
        "bundle_id": args.bundle_id,
        "version": args.version,
        "seal_ref": args.seal_ref,
        "signature_ref": args.signature_ref,
        "verification_tool": args.verification_tool,
        "status": verify_status,
        "summary": {
            "status": status,
            "message": evidence.get("message"),
            "verified_root_hash": verified_root_hash,
            "seal_root_hash_matches": seal_root_hash_matches,
            "evidence_count": evidence.get("evidence_count"),
        },
        "seal_root_hash": args.seal_root_hash,
        "key_ref": evidence.get("key_ref") or args.key_ref,
        "release_evidence_index_ref": args.release_evidence_index_ref,
    }

    text = json.dumps(record, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
