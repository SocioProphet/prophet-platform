#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Fog Stack wider release proof pipeline")
    parser.add_argument("--tool", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--validation-record", required=True, type=Path)
    parser.add_argument("--signature-verification-record", required=True, type=Path)
    parser.add_argument("--signature-trust-record", required=True, type=Path)
    parser.add_argument("--seal", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--signature-ref", required=True)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--seal-crypto-record", required=True, type=Path)
    parser.add_argument("--evidence-index", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="External seal verifier command, e.g. cosign verify ...")
    args = parser.parse_args()

    if not args.command:
        raise SystemExit("ERR: external seal verifier command is required after '--'")

    proof_cmd = [
        "python3",
        "tools/run_fogstack_release_proof_pipeline.py",
        "--tool", args.tool,
        "--seal", str(args.seal),
        "--bundle-id", args.bundle_id,
        "--version", args.version,
        "--signature-ref", args.signature_ref,
        "--evidence-output", str(args.evidence_output),
        "--seal-crypto-record", str(args.seal_crypto_record),
        "--evidence-index", str(args.evidence_index),
        "--",
    ] + args.command
    proof = subprocess.run(proof_cmd)
    if proof.returncode != 0:
        raise SystemExit(proof.returncode)

    wider_cmd = [
        "python3",
        "tools/link_fogstack_wider_release_graph.py",
        "--manifest", str(args.manifest),
        "--validation-record", str(args.validation_record),
        "--signature-verification-record", str(args.signature_verification_record),
        "--signature-trust-record", str(args.signature_trust_record),
        "--release-seal", str(args.seal),
        "--release-seal-crypto-record", str(args.seal_crypto_record),
    ]
    wider = subprocess.run(wider_cmd)
    if wider.returncode != 0:
        raise SystemExit(wider.returncode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
