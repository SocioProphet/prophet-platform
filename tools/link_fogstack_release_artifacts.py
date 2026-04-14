#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Link Fog Stack release artifacts by inserting backlink refs")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--validation-record", required=True, type=Path)
    parser.add_argument("--signature-verification-record", required=True, type=Path)
    parser.add_argument("--signature-trust-record", required=True, type=Path)
    parser.add_argument("--evidence-index-ref", required=True)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    validation = load_json(args.validation_record)
    sig_verify = load_json(args.signature_verification_record)
    sig_trust = load_json(args.signature_trust_record)

    manifest["validation_record_ref"] = str(args.validation_record)
    manifest["signature_verification_record_ref"] = str(args.signature_verification_record)
    manifest["signature_trust_record_ref"] = str(args.signature_trust_record)
    manifest["release_evidence_index_ref"] = args.evidence_index_ref

    validation["manifest_ref"] = str(args.manifest)
    validation["signature_verification_record_ref"] = str(args.signature_verification_record)
    validation["signature_trust_record_ref"] = str(args.signature_trust_record)
    validation["release_evidence_index_ref"] = args.evidence_index_ref

    sig_verify["validation_record_ref"] = str(args.validation_record)
    sig_verify["signature_trust_record_ref"] = str(args.signature_trust_record)
    sig_verify["release_evidence_index_ref"] = args.evidence_index_ref

    sig_trust["validation_record_ref"] = str(args.validation_record)
    sig_trust["signature_verification_record_ref"] = str(args.signature_verification_record)
    sig_trust["release_evidence_index_ref"] = args.evidence_index_ref

    write_json(args.manifest, manifest)
    write_json(args.validation_record, validation)
    write_json(args.signature_verification_record, sig_verify)
    write_json(args.signature_trust_record, sig_trust)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
