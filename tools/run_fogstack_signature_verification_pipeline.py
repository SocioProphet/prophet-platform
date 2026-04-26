#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2
EXIT_INVALID = 3


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing JSON input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON input: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def nested_summary_value(data: dict[str, Any], key: str) -> Any:
    summary = data.get("summary")
    if isinstance(summary, dict) and key in summary:
        return summary.get(key)
    return None


def normalize_status(raw_status: Any) -> str:
    if raw_status in {"pass", "warn", "fail"}:
        return str(raw_status)
    if raw_status in {"verified", "success", "ok", True}:
        return "pass"
    if raw_status in {"warning", "shape-only"}:
        return "warn"
    if raw_status in {"failed", "error", False}:
        return "fail"
    return "warn"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Fog Stack signature verification pipeline from external evidence to cryptographic verification record")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--external-evidence", dest="external_evidence", type=Path, default=None)
    parser.add_argument("--raw-evidence", dest="external_evidence", type=Path, default=None, help="deprecated alias for --external-evidence")
    parser.add_argument("--tool", default="cosign", choices=["cosign", "sigstore", "other"])
    parser.add_argument("--bundle-id", default=None)
    parser.add_argument("--version", default=None)
    parser.add_argument("--signature-ref", default=None)
    parser.add_argument("--key-ref", default=None)
    parser.add_argument("--validation-record-ref", default=None)
    parser.add_argument("--signature-verification-record-ref", default=None)
    parser.add_argument("--signature-trust-record-ref", default=None)
    parser.add_argument("--release-evidence-index-ref", default=None)
    parser.add_argument("--normalized-output", type=Path, default=None)
    parser.add_argument("--record-output", type=Path, default=None)
    parser.add_argument("--out", dest="record_output", type=Path, default=None, help="alias for --record-output")
    args = parser.parse_args()

    if args.external_evidence is None:
        print("ERR: --external-evidence is required", flush=True)
        return EXIT_INVALID

    try:
        manifest = load_json(args.manifest)
        raw = load_json(args.external_evidence)
    except ValueError as exc:
        print(f"ERR: {exc}", flush=True)
        return EXIT_INVALID

    manifest_digest = manifest.get("bundle_digest")
    verified_digest = raw.get("verified_digest") or nested_summary_value(raw, "verified_digest")
    raw_status = raw.get("status") or nested_summary_value(raw, "status") or "warn"
    norm_status = normalize_status(raw_status)

    if not isinstance(manifest_digest, str) or not manifest_digest:
        print("ERR: manifest.bundle_digest is required", flush=True)
        return EXIT_INVALID
    if not isinstance(verified_digest, str) or not verified_digest:
        print("ERR: external evidence verified_digest is required", flush=True)
        return EXIT_INVALID

    digest_match = manifest_digest == verified_digest
    if norm_status == "pass" and digest_match:
        record_status = "verified"
        exit_code = EXIT_PASS
    elif norm_status == "warn" and digest_match:
        record_status = "shape-only"
        exit_code = EXIT_WARN
    else:
        record_status = "failed"
        exit_code = EXIT_FAIL

    normalized = {
        "kind": "FogStackExternalSignatureVerificationEvidence",
        "schema_version": "v0.1",
        "tool": args.tool,
        "status": norm_status,
        "message": raw.get("message") or nested_summary_value(raw, "message"),
        "verified_digest": verified_digest,
        "evidence_count": raw.get("evidence_count") or nested_summary_value(raw, "evidence_count"),
        "key_ref": raw.get("key_ref") or args.key_ref,
        "raw_ref": str(args.external_evidence),
    }

    record = {
        "kind": "FogStackCryptographicSignatureVerificationRecord",
        "schema_version": "v0.1",
        "bundle_id": args.bundle_id or manifest.get("bundle_id"),
        "version": args.version or manifest.get("version"),
        "manifest_ref": str(args.manifest),
        "signature_ref": args.signature_ref or ((manifest.get("signature") or {}).get("ref")) or "",
        "verification_tool": args.tool,
        "status": record_status,
        "summary": {
            "status": norm_status if exit_code != EXIT_FAIL else "fail",
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

    if not record["bundle_id"] or not record["version"]:
        print("ERR: bundle_id and version must be supplied by args or manifest", flush=True)
        return EXIT_INVALID

    if args.normalized_output:
        args.normalized_output.parent.mkdir(parents=True, exist_ok=True)
        args.normalized_output.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    if args.record_output:
        args.record_output.parent.mkdir(parents=True, exist_ok=True)
        args.record_output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if not args.normalized_output and not args.record_output:
        print(json.dumps({"normalized": normalized, "record": record}, indent=2))

    if exit_code == EXIT_FAIL:
        print("ERR: Fog Stack signature verification failed", flush=True)
    elif exit_code == EXIT_WARN:
        print("WARN: Fog Stack signature verification produced shape-only record", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
