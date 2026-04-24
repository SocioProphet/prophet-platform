#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an external signature verifier and feed the Fog Stack verification pipeline")
    parser.add_argument("--tool", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--raw-output", required=True, type=Path)
    parser.add_argument("--normalized-output", required=True, type=Path)
    parser.add_argument("--record-output", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="External verifier command, e.g. cosign verify ...")
    args = parser.parse_args()

    if not args.command:
        raise SystemExit("ERR: external verifier command is required after '--'")

    proc = subprocess.run(args.command, capture_output=True, text=True)

    if proc.stdout.strip():
        args.raw_output.write_text(proc.stdout, encoding="utf-8")
    else:
        args.raw_output.write_text(json.dumps({
            "status": "fail" if proc.returncode else "warn",
            "message": proc.stderr.strip() or "external verifier produced no stdout",
            "evidence_count": 0,
        }, indent=2) + "\n", encoding="utf-8")

    normalize_cmd = [
        "python3",
        "tools/normalize_fogstack_signature_verification_evidence.py",
        "--input", str(args.raw_output),
        "--tool", args.tool,
        "--output", str(args.normalized_output),
    ]
    norm = subprocess.run(normalize_cmd)
    if norm.returncode != 0:
        raise SystemExit(norm.returncode)

    pipeline_cmd = [
        "python3",
        "tools/run_fogstack_signature_verification_pipeline.py",
        "--manifest", str(args.manifest),
        "--raw-evidence", str(args.normalized_output),
        "--tool", args.tool,
        "--bundle-id", args.bundle_id,
        "--version", args.version,
        "--record-output", str(args.record_output),
    ]
    pipe = subprocess.run(pipeline_cmd)
    if pipe.returncode != 0:
        raise SystemExit(pipe.returncode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
