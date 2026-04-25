#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def verify(path: Path, signature: Path, public_key: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-verify",
            str(public_key),
            "-signature",
            str(signature),
            str(path),
        ],
        capture_output=True,
        text=True,
    )


def unsigned_seal_path(seal: dict, directory: Path) -> Path:
    canonical = dict(seal)
    canonical.pop("signed", None)
    canonical.pop("signature", None)
    canonical.pop("release_evidence_index_ref", None)
    canonical.pop("release_seal_cryptographic_verification_record_ref", None)
    path = directory / "unsigned-release-seal.json"
    path.write_text(json.dumps(canonical, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Fog Stack release seal signature with openssl and emit normalized JSON")
    parser.add_argument("--seal", required=True, type=Path)
    parser.add_argument("--signature", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--key-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if shutil.which("openssl") is None:
        raise SystemExit("ERR: openssl is required")

    seal = load_json(args.seal)
    proc = verify(args.seal, args.signature, args.public_key)
    if proc.returncode != 0:
        with tempfile.TemporaryDirectory() as tmp:
            canonical_path = unsigned_seal_path(seal, Path(tmp))
            proc = verify(canonical_path, args.signature, args.public_key)

    ok = proc.returncode == 0
    evidence = {
        "status": "pass" if ok else "fail",
        "message": (proc.stdout or proc.stderr).strip() or ("verified" if ok else "verification failed"),
        "verified_root_hash": seal.get("release_root_hash") if ok else None,
        "evidence_count": 1,
        "key_ref": args.key_ref or str(args.public_key),
    }

    text = json.dumps(evidence, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
