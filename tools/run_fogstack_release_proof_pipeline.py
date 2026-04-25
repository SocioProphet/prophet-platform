#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def normalize_command(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Fog Stack release proof pipeline for a sealed bundle")
    parser.add_argument("--tool", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--seal", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--signature-ref", required=True)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--seal-crypto-record", required=True, type=Path)
    parser.add_argument("--evidence-index", required=True, type=Path)
    parser.add_argument("--canonical-contract-surface-ref")
    parser.add_argument("--canonical-deployment-surface-ref")
    parser.add_argument("--canonical-runtime-surface-ref")
    parser.add_argument("--canonical-policy-surface-ref")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="External seal verifier command, e.g. cosign verify ...")
    args = parser.parse_args()

    command = normalize_command(args.command)
    if not command:
        raise SystemExit("ERR: external seal verifier command is required after '--'")

    run_cmd = [
        "python3",
        "tools/run_external_fogstack_release_seal_verifier.py",
        "--tool", args.tool,
        "--seal", str(args.seal),
        "--bundle-id", args.bundle_id,
        "--version", args.version,
        "--signature-ref", args.signature_ref,
        "--evidence-output", str(args.evidence_output),
        "--record-output", str(args.seal_crypto_record),
        "--",
    ] + command
    proc = subprocess.run(run_cmd)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    link_cmd = [
        "python3",
        "tools/link_fogstack_release_seal_artifacts.py",
        "--seal", str(args.seal),
        "--seal-crypto-record", str(args.seal_crypto_record),
        "--evidence-index", str(args.evidence_index),
    ]
    if args.canonical_contract_surface_ref is not None:
        link_cmd += ["--canonical-contract-surface-ref", args.canonical_contract_surface_ref]
    if args.canonical_deployment_surface_ref is not None:
        link_cmd += ["--canonical-deployment-surface-ref", args.canonical_deployment_surface_ref]
    if args.canonical_runtime_surface_ref is not None:
        link_cmd += ["--canonical-runtime-surface-ref", args.canonical_runtime_surface_ref]
    if args.canonical_policy_surface_ref is not None:
        link_cmd += ["--canonical-policy-surface-ref", args.canonical_policy_surface_ref]

    link = subprocess.run(link_cmd)
    if link.returncode != 0:
        raise SystemExit(link.returncode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
