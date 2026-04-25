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
    parser = argparse.ArgumentParser(description="Link Fog Stack wider release graph artifacts")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--validation-record", required=True, type=Path)
    parser.add_argument("--signature-verification-record", required=True, type=Path)
    parser.add_argument("--signature-trust-record", required=True, type=Path)
    parser.add_argument("--release-seal", required=True, type=Path)
    parser.add_argument("--release-seal-crypto-record", required=True, type=Path)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    validation = load_json(args.validation_record)
    sig_verify = load_json(args.signature_verification_record)
    sig_trust = load_json(args.signature_trust_record)

    for obj in (manifest, validation, sig_verify, sig_trust):
        obj["release_seal_ref"] = str(args.release_seal)
        obj["release_seal_cryptographic_verification_record_ref"] = str(args.release_seal_crypto_record)

    write_json(args.manifest, manifest)
    write_json(args.validation_record, validation)
    write_json(args.signature_verification_record, sig_verify)
    write_json(args.signature_trust_record, sig_trust)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
