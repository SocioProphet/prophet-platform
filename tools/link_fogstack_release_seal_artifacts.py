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
    parser = argparse.ArgumentParser(description="Link Fog Stack release seal artifacts by inserting backlink refs")
    parser.add_argument("--seal", required=True, type=Path)
    parser.add_argument("--seal-crypto-record", required=True, type=Path)
    parser.add_argument("--evidence-index", required=True, type=Path)
    parser.add_argument("--canonical-contract-surface-ref")
    parser.add_argument("--canonical-deployment-surface-ref")
    parser.add_argument("--canonical-runtime-surface-ref")
    parser.add_argument("--canonical-policy-surface-ref")
    args = parser.parse_args()

    seal = load_json(args.seal)
    seal_crypto = load_json(args.seal_crypto_record)
    evidence_index = load_json(args.evidence_index)

    seal["release_evidence_index_ref"] = str(args.evidence_index)
    seal["release_seal_cryptographic_verification_record_ref"] = str(args.seal_crypto_record)

    seal_crypto["release_evidence_index_ref"] = str(args.evidence_index)

    evidence_index["release_seal_ref"] = str(args.seal)
    evidence_index["release_seal_cryptographic_verification_record_ref"] = str(args.seal_crypto_record)

    if args.canonical_contract_surface_ref is not None:
        evidence_index["canonical_contract_surface_ref"] = args.canonical_contract_surface_ref
    if args.canonical_deployment_surface_ref is not None:
        evidence_index["canonical_deployment_surface_ref"] = args.canonical_deployment_surface_ref
    if args.canonical_runtime_surface_ref is not None:
        evidence_index["canonical_runtime_surface_ref"] = args.canonical_runtime_surface_ref
    if args.canonical_policy_surface_ref is not None:
        evidence_index["canonical_policy_surface_ref"] = args.canonical_policy_surface_ref

    write_json(args.seal, seal)
    write_json(args.seal_crypto_record, seal_crypto)
    write_json(args.evidence_index, evidence_index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
