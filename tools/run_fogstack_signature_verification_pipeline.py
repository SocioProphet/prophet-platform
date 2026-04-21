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
    parser = argparse.ArgumentParser(description="Run the Fog Stack signature verification pipeline from external evidence to cryptographic verification record")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--raw-evidence", required=True, type=Path)
    parser.add_argument("--tool", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--signature-ref", default=None)
    parser.add_argument("--key-ref", default=None)
    parser.add_argument("--validation-record-ref", default=None)
    parser.add_argument("--signature-verification-record-ref", default=None)
    parser.add_argument("--signature-trust-record-ref", default=None)
    parser.add_argument("--release-evidence-index-ref", default=None)
    parser.add_argument("--normalized-output", type=Path, default=None)
    parser.add_argument("--record-output", type=Path, default=None)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    raw = load_json(args.raw_evidence)

    normalized = {
        "kind": "FogStackExternalSignatureVerificationEvidence",
        "schema_version": "v0.1",
        "tool": args.tool,
        "status": raw.get("status") or (raw.get("summary") or {}).get("status") or "unknown",
        "message": raw.get("message") or (raw.get("summary") or {}).get("message"),
        "verified_digest": raw.get("verified_digest") or (raw.get("summary") or {}).get("verified_digest"),
        "evidence_count": raw.get("evidence_count") or (raw.get("summary") or {}).get("evidence_count"),
        "key_ref": raw.get("key_ref") or args.key_ref,
        "raw_ref": str(args.raw_evidence),
    }

    manifest_digest = manifest.get("bundle_digest")
    verified_digest = normalized.get("verified_digest")
    digest_match = None
    if isinstance(manifest_digest, str) and isinstance(verified_digest, str):
        digest_match = manifest_digest == verified_digest

    norm_status = normalized["status"]
    if norm_status == "pass" and digest_match is True:
        record_status = "verified"
    elif norm_status == "fail" or digest_match is False:
        record_status = "failed"
    else:
        record_status = "shape-only"

    record = {
        "kind": "FogStackCryptographicSignatureVerificationRecord",
        "schema_version": "v0.1",
        "bundle_id": args.bundle_id,
        "version": args.version,
        "manifest_ref": str(args.manifest),
        "signature_ref": args.signature_ref or ((manifest.get("signature") or {}).get("ref")),
        "verification_tool": args.tool,
        "status": record_status,
        "summary": {
            "status": norm_status,
            "message": normalized.get("message"),
            "verified_digest": verified_digest,
            "evidence_count": normalized.get("evidence_count"),
            "manifest_digest_matches": digest_match,
        },
        "manifest_digest": manifest_digest,
        "key_ref": normalized.get("key_ref"),
        "validation_record_ref": args.validation_record_ref,
        "signature_verification_record_ref": args.signature_verification_record_ref,
        "signature_trust_record_ref": args.signature_trust_record_ref,
        "release_evidence_index_ref": args.release_evidence_index_ref,
    }

    if args.normalized_output:
        args.normalized_output.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    if args.record_output:
        args.record_output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if not args.normalized_output and not args.record_output:
        print(json.dumps({"normalized": normalized, "record": record}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
