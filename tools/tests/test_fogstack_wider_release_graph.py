from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_wider_release_graph_linker_adds_seal_refs(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    validation = tmp_path / "validation.record.json"
    sig_verify = tmp_path / "signature-verification.record.json"
    sig_trust = tmp_path / "signature-trust.record.json"
    seal = tmp_path / "release.seal.json"
    seal_crypto = tmp_path / "release.seal.crypto-verification.record.json"

    _write_json(manifest, {
        "kind": "FogStackBundleManifest",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "bundle": "bundles/fogstack.access-v0.1.yaml",
        "rulepack": "conformance/rulepacks/fogstack.access-v0.1.yaml",
        "bundle_digest": "sha256:test",
        "rulepack_digest": "sha256:test",
        "channel": "preview",
        "support_state": "community",
        "signed": False,
    })
    _write_json(validation, {
        "kind": "FogStackValidationRecord",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "validation_path": "tools/validate_fogstack.py",
        "source": "local",
        "summary": {"status": "pass", "exit_code": 0},
    })
    _write_json(sig_verify, {
        "kind": "FogStackSignatureVerificationRecord",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "manifest_ref": str(manifest),
        "status": "verified",
        "summary": {"status": "pass", "exit_code": 0, "checks_run": 1},
        "signature_ref": "artifact://release/fogstack.access.sig",
    })
    _write_json(sig_trust, {
        "kind": "FogStackSignatureTrustRecord",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "manifest_ref": str(manifest),
        "signature_ref": "artifact://release/fogstack.access.sig",
        "verification_method": "cosign",
        "status": "verified",
        "summary": {"status": "pass", "message": None, "evidence_count": 1},
    })
    _write_json(seal, {
        "kind": "FogStackReleaseSeal",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "algorithm": "sha256",
        "release_root_hash": "sha256:test-seal-root",
        "artifact_hashes": [],
        "signed": True,
        "signature": {"type": "cosign", "ref": "artifact://release/fogstack.access.seal.sig"},
    })
    _write_json(seal_crypto, {
        "kind": "FogStackReleaseSealCryptographicVerificationRecord",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "seal_ref": str(seal),
        "signature_ref": "artifact://release/fogstack.access.seal.sig",
        "verification_tool": "cosign",
        "status": "verified",
        "summary": {
            "status": "pass",
            "message": None,
            "verified_root_hash": "sha256:test-seal-root",
            "seal_root_hash_matches": True,
            "evidence_count": 1,
        },
        "seal_root_hash": "sha256:test-seal-root",
    })

    cmd = [
        sys.executable,
        "tools/link_fogstack_wider_release_graph.py",
        "--manifest", str(manifest),
        "--validation-record", str(validation),
        "--signature-verification-record", str(sig_verify),
        "--signature-trust-record", str(sig_trust),
        "--release-seal", str(seal),
        "--release-seal-crypto-record", str(seal_crypto),
    ]
    subprocess.run(cmd, check=True)

    for path in (manifest, validation, sig_verify, sig_trust):
        data = _read_json(path)
        assert data["release_seal_ref"] == str(seal)
        assert data["release_seal_cryptographic_verification_record_ref"] == str(seal_crypto)
