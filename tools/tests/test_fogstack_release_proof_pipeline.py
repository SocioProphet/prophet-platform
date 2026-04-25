from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_proof_pipeline_links_seal_artifacts(tmp_path: Path) -> None:
    seal = tmp_path / "fogstack.access.seal.json"
    seal_root_hash = "sha256:test-seal-root"
    _write_json(
        seal,
        {
            "kind": "FogStackReleaseSeal",
            "schema_version": "v0.1",
            "bundle_id": "fogstack.access",
            "version": "0.1.0",
            "algorithm": "sha256",
            "release_root_hash": seal_root_hash,
            "artifact_hashes": [],
            "signed": True,
            "signature": {"type": "cosign", "ref": "artifact://release/fogstack.access-v0.1.seal.sig"},
        },
    )

    evidence_index = tmp_path / "fogstack.access.evidence.index.json"
    _write_json(
        evidence_index,
        {
            "kind": "FogStackReleaseEvidenceIndex",
            "schema_version": "v0.1",
            "bundle_id": "fogstack.access",
            "version": "0.1.0",
            "manifest_ref": "releases/manifests/fogstack.access-v0.1.manifest.json",
            "validation_record_ref": "releases/evidence/fogstack.access-v0.1.validation.record.json",
            "signature_verification_record_ref": "releases/evidence/fogstack.access-v0.1.signature-verification.record.json",
            "signature_trust_record_ref": "releases/evidence/fogstack.access-v0.1.signature-trust.record.json",
            "notes": None,
        },
    )

    mock_verify = tmp_path / "mock_verify.py"
    mock_verify.write_text(
        "import json, os\n"
        "print(json.dumps({\"status\": \"pass\", \"verified_root_hash\": os.environ['SEAL_HASH'], \"evidence_count\": 1}))\n",
        encoding="utf-8",
    )

    evidence_output = tmp_path / "fogstack.access.seal.verify.json"
    seal_crypto_record = tmp_path / "fogstack.access.seal.crypto-verification.record.json"

    env = os.environ.copy()
    env["SEAL_HASH"] = seal_root_hash

    contract_ref = "https://github.com/SocioProphet/api-spec/tree/master/fog"
    deployment_ref = "https://github.com/SocioProphet/manifests/tree/master/fog"
    runtime_ref = "https://github.com/SocioProphet/cloudshell-fog"
    policy_ref = "https://github.com/SocioProphet/policy-fabric/tree/main/contracts"

    cmd = [
        sys.executable,
        "tools/run_fogstack_release_proof_pipeline.py",
        "--tool",
        "cosign",
        "--seal",
        str(seal),
        "--bundle-id",
        "fogstack.access",
        "--version",
        "0.1.0",
        "--signature-ref",
        "artifact://release/fogstack.access-v0.1.seal.sig",
        "--evidence-output",
        str(evidence_output),
        "--seal-crypto-record",
        str(seal_crypto_record),
        "--evidence-index",
        str(evidence_index),
        "--canonical-contract-surface-ref",
        contract_ref,
        "--canonical-deployment-surface-ref",
        deployment_ref,
        "--canonical-runtime-surface-ref",
        runtime_ref,
        "--canonical-policy-surface-ref",
        policy_ref,
        "--",
        sys.executable,
        str(mock_verify),
    ]
    subprocess.run(cmd, check=True, env=env)

    crypto = _read_json(seal_crypto_record)
    assert crypto["status"] == "verified"
    assert crypto["summary"]["seal_root_hash_matches"] is True

    seal_after = _read_json(seal)
    assert seal_after["release_evidence_index_ref"] == str(evidence_index)
    assert seal_after["release_seal_cryptographic_verification_record_ref"] == str(seal_crypto_record)

    index_after = _read_json(evidence_index)
    assert index_after["release_seal_ref"] == str(seal)
    assert index_after["release_seal_cryptographic_verification_record_ref"] == str(seal_crypto_record)
    assert index_after["canonical_contract_surface_ref"] == contract_ref
    assert index_after["canonical_deployment_surface_ref"] == deployment_ref
    assert index_after["canonical_runtime_surface_ref"] == runtime_ref
    assert index_after["canonical_policy_surface_ref"] == policy_ref
