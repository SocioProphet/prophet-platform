#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def normalize_command(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an external verifier for a Fog Stack release seal and emit the cryptographic verification record")
    parser.add_argument("--tool", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--seal", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--signature-ref", required=True)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--record-output", required=True, type=Path)
    parser.add_argument("--key-ref", default=None)
    parser.add_argument("--release-evidence-index-ref", default=None)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="External verifier command, e.g. cosign verify ...")
    args = parser.parse_args()

    command = normalize_command(args.command)
    if not command:
        raise SystemExit("ERR: external verifier command is required after '--'")

    seal = load_json(args.seal)
    seal_root_hash = seal.get("release_root_hash")

    proc = subprocess.run(command, capture_output=True, text=True)

    if proc.stdout.strip():
        try:
            raw = json.loads(proc.stdout)
        except Exception:
            raw = {
                "status": "fail" if proc.returncode else "warn",
                "message": "external verifier stdout was not JSON",
                "verified_root_hash": None,
                "evidence_count": 0,
                "key_ref": args.key_ref,
            }
    else:
        raw = {
            "status": "fail" if proc.returncode else "warn",
            "message": proc.stderr.strip() or "external verifier produced no stdout",
            "verified_root_hash": None,
            "evidence_count": 0,
            "key_ref": args.key_ref,
        }

    evidence = {
        "status": raw.get("status") or (raw.get("summary") or {}).get("status") or "unknown",
        "message": raw.get("message") or (raw.get("summary") or {}).get("message"),
        "verified_root_hash": raw.get("verified_root_hash") or (raw.get("summary") or {}).get("verified_root_hash"),
        "evidence_count": raw.get("evidence_count") or (raw.get("summary") or {}).get("evidence_count"),
        "key_ref": raw.get("key_ref") or args.key_ref,
    }
    args.evidence_output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    emit_cmd = [
        "python3",
        "tools/emit_fogstack_release_seal_cryptographic_verification_record.py",
        "--verification-evidence", str(args.evidence_output),
        "--bundle-id", args.bundle_id,
        "--version", args.version,
        "--seal-ref", str(args.seal),
        "--signature-ref", args.signature_ref,
        "--verification-tool", args.tool,
        "--output", str(args.record_output),
    ]
    if isinstance(seal_root_hash, str):
        emit_cmd.extend(["--seal-root-hash", seal_root_hash])
    if args.key_ref:
        emit_cmd.extend(["--key-ref", args.key_ref])
    if args.release_evidence_index_ref:
        emit_cmd.extend(["--release-evidence-index-ref", args.release_evidence_index_ref])

    emit = subprocess.run(emit_cmd)
    if emit.returncode != 0:
        raise SystemExit(emit.returncode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
