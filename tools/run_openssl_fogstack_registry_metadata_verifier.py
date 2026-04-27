#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SUPPORTED_KINDS = {
    "FogStackFilesystemRegistryRoot": "registry_root",
    "FogStackRegistryRollbackRevocationIndex": "rollback_revocation_index",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_payload(metadata: dict[str, Any]) -> bytes:
    payload = dict(metadata)
    payload["signatures"] = []
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def find_signature(metadata: dict[str, Any], signature_ref: str | None) -> dict[str, Any]:
    signatures = metadata.get("signatures") or []
    if not isinstance(signatures, list):
        raise SystemExit("ERR: metadata signatures must be a list")
    candidates = [item for item in signatures if isinstance(item, dict)]
    if signature_ref:
        candidates = [item for item in candidates if item.get("signature_ref") == signature_ref]
    candidates = [item for item in candidates if item.get("algorithm") == "openssl-rsa-sha256"]
    if not candidates:
        raise SystemExit("ERR: no openssl-rsa-sha256 signature found")
    if len(candidates) > 1:
        raise SystemExit("ERR: multiple matching openssl-rsa-sha256 signatures found")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Fog Stack registry metadata canonical signature with OpenSSL")
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--signature", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--signature-ref", default=None)
    parser.add_argument("--key-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    metadata = load_json(args.metadata)
    kind = metadata.get("kind")
    if kind not in SUPPORTED_KINDS:
        raise SystemExit(f"ERR: unsupported registry metadata kind: {kind}")

    signature_entry = find_signature(metadata, args.signature_ref)
    expected_ref = signature_entry.get("signature_ref")
    if args.signature_ref and expected_ref != args.signature_ref:
        raise SystemExit("ERR: requested signature ref does not match metadata")

    payload = canonical_payload(metadata)
    with tempfile.NamedTemporaryFile() as handle:
        handle.write(payload)
        handle.flush()
        proc = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(args.public_key),
                "-signature",
                str(args.signature),
                handle.name,
            ],
            capture_output=True,
            text=True,
        )

    passed = proc.returncode == 0
    result = {
        "kind": "FogStackRegistryMetadataSignatureVerification",
        "schema_version": "v0.1",
        "metadata_kind": kind,
        "metadata_ref": str(args.metadata),
        "metadata_payload_digest": sha256_bytes(payload),
        "signature_ref": expected_ref,
        "signature_file_ref": str(args.signature),
        "verification_tool": "openssl",
        "key_ref": args.key_ref or str(args.public_key),
        "status": "pass" if passed else "fail",
        "message": proc.stdout.strip() or proc.stderr.strip() or None,
    }
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
