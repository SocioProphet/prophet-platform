from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def canonical_payload(metadata: dict) -> bytes:
    payload = dict(metadata)
    payload["signatures"] = []
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_signed_metadata(tmp_path: Path, metadata: dict, name: str) -> tuple[Path, Path, Path]:
    if not shutil.which("openssl"):
        pytest.skip("openssl is not available")

    private_key = tmp_path / f"{name}.private.pem"
    public_key = tmp_path / f"{name}.public.pem"
    payload = tmp_path / f"{name}.payload.json"
    signature = tmp_path / f"{name}.sig"
    metadata_path = tmp_path / f"{name}.json"

    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", str(private_key)], check=True)
    subprocess.run(["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)], check=True)
    payload.write_bytes(canonical_payload(metadata))
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(private_key), "-out", str(signature), str(payload)], check=True)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata_path, signature, public_key


def registry_root_metadata() -> dict:
    return {
        "kind": "FogStackFilesystemRegistryRoot",
        "schema_version": "v0.1",
        "registry_uri": "file://registry/fogstack",
        "generated_at": "2026-04-27T00:00:00Z",
        "releases": [],
        "root_digest": "sha256:" + "a" * 64,
        "signatures": [
            {
                "key_id": "test-registry-key",
                "algorithm": "openssl-rsa-sha256",
                "signature_ref": "registry-root.sig",
            }
        ],
    }


def lifecycle_metadata() -> dict:
    return {
        "kind": "FogStackRegistryRollbackRevocationIndex",
        "schema_version": "v0.1",
        "registry_uri": "file://registry/fogstack",
        "generated_at": "2026-04-27T00:00:00Z",
        "rollback_targets": [],
        "revocations": [],
        "index_digest": "sha256:" + "b" * 64,
        "signatures": [
            {
                "key_id": "test-registry-key",
                "algorithm": "openssl-rsa-sha256",
                "signature_ref": "lifecycle.sig",
            }
        ],
    }


def run_verify(metadata_path: Path, signature: Path, public_key: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "tools/run_openssl_fogstack_registry_metadata_verifier.py",
            "--metadata",
            str(metadata_path),
            "--signature",
            str(signature),
            "--public-key",
            str(public_key),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )


def test_openssl_registry_root_metadata_verifier_accepts_valid_signature(tmp_path: Path) -> None:
    metadata_path, signature, public_key = write_signed_metadata(tmp_path, registry_root_metadata(), "registry-root")
    output = tmp_path / "verification.json"

    proc = run_verify(metadata_path, signature, public_key, output)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["kind"] == "FogStackRegistryMetadataSignatureVerification"
    assert result["metadata_kind"] == "FogStackFilesystemRegistryRoot"
    assert result["status"] == "pass"
    assert result["metadata_payload_digest"].startswith("sha256:")


def test_openssl_lifecycle_metadata_verifier_accepts_valid_signature(tmp_path: Path) -> None:
    metadata_path, signature, public_key = write_signed_metadata(tmp_path, lifecycle_metadata(), "lifecycle")
    output = tmp_path / "verification.json"

    proc = run_verify(metadata_path, signature, public_key, output)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["metadata_kind"] == "FogStackRegistryRollbackRevocationIndex"
    assert result["status"] == "pass"


def test_openssl_registry_metadata_verifier_rejects_tamper(tmp_path: Path) -> None:
    metadata = registry_root_metadata()
    metadata_path, signature, public_key = write_signed_metadata(tmp_path, metadata, "registry-root")
    output = tmp_path / "verification.json"

    tampered = json.loads(metadata_path.read_text(encoding="utf-8"))
    tampered["registry_uri"] = "file://registry/tampered"
    metadata_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    proc = run_verify(metadata_path, signature, public_key, output)
    assert proc.returncode == 1
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "fail"


def test_openssl_registry_metadata_verifier_rejects_shape_only_signature(tmp_path: Path) -> None:
    metadata = registry_root_metadata()
    metadata["signatures"][0]["algorithm"] = "shape-only"
    metadata_path = tmp_path / "registry-root.json"
    signature = tmp_path / "registry-root.sig"
    public_key = tmp_path / "registry-root.public.pem"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    signature.write_text("not-a-real-signature", encoding="utf-8")
    public_key.write_text("not-a-real-key", encoding="utf-8")

    proc = run_verify(metadata_path, signature, public_key, tmp_path / "verification.json")
    assert proc.returncode != 0
}
