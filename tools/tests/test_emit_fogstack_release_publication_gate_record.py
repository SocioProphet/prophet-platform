from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_policy(path: Path) -> None:
    path.write_text(
        'schema_version: "fogstack.release-publication-gate-policy/v0.1"\n'
        'kind: "FogStackReleasePublicationGatePolicy"\n'
        'requirements:\n'
        '  approval_status: "approved"\n'
        '  approval_signature_status: "pass"\n'
        '  require_release_identity: true\n'
        'allowed_release_identities:\n'
        '  - id: "github-actions"\n'
        '    issuer: "github-actions"\n'
        '    subject: "SocioProphet/prophet-platform/.github/workflows/fogstack-manifest-promotion.yml"\n',
        encoding="utf-8",
    )


def test_release_publication_gate_allows_valid_inputs(tmp_path: Path) -> None:
    publication = tmp_path / "manifest-publication-set.json"
    approval = tmp_path / "approval.record.json"
    sig_verify = tmp_path / "approval.signature-verification.json"
    identity = tmp_path / "release-identity.json"
    policy = tmp_path / "publication-gate-policy.yaml"
    output = tmp_path / "publication-gate.record.json"

    _write_json(publication, {
        "kind": "FogStackManifestPublicationSet",
        "schema_version": "v0.1",
        "manifests": [],
    })
    _write_json(approval, {
        "kind": "FogStackManifestPromotionApprovalRecord",
        "status": "approved",
    })
    _write_json(sig_verify, {
        "kind": "FogStackManifestPromotionApprovalSignatureVerification",
        "status": "pass",
    })
    _write_json(identity, {
        "kind": "FogStackReleaseIdentity",
        "schema_version": "v0.1",
        "id": "github-actions",
        "issuer": "github-actions",
        "subject": "SocioProphet/prophet-platform/.github/workflows/fogstack-manifest-promotion.yml",
    })
    _write_policy(policy)

    subprocess.run([
        sys.executable,
        "tools/emit_fogstack_release_publication_gate_record.py",
        "--publication-set", str(publication),
        "--approval-record", str(approval),
        "--approval-signature-verification", str(sig_verify),
        "--release-identity", str(identity),
        "--policy-catalog", str(policy),
        "--output", str(output),
    ], check=True)

    gate = json.loads(output.read_text(encoding="utf-8"))
    assert gate["kind"] == "FogStackReleasePublicationGateRecord"
    assert gate["status"] == "pass"
    assert all(check["status"] == "pass" for check in gate["checks"])


def test_release_publication_gate_rejects_bad_identity(tmp_path: Path) -> None:
    publication = tmp_path / "manifest-publication-set.json"
    approval = tmp_path / "approval.record.json"
    sig_verify = tmp_path / "approval.signature-verification.json"
    identity = tmp_path / "release-identity.json"
    policy = tmp_path / "publication-gate-policy.yaml"

    _write_json(publication, {"kind": "FogStackManifestPublicationSet"})
    _write_json(approval, {"status": "approved"})
    _write_json(sig_verify, {"status": "pass"})
    _write_json(identity, {
        "id": "unknown",
        "issuer": "github-actions",
        "subject": "SocioProphet/prophet-platform/.github/workflows/fogstack-manifest-promotion.yml",
    })
    _write_policy(policy)

    proc = subprocess.run([
        sys.executable,
        "tools/emit_fogstack_release_publication_gate_record.py",
        "--publication-set", str(publication),
        "--approval-record", str(approval),
        "--approval-signature-verification", str(sig_verify),
        "--release-identity", str(identity),
        "--policy-catalog", str(policy),
    ])
    assert proc.returncode != 0
