from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_fogstack_local_demo_access(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"

    subprocess.run([
        sys.executable,
        "tools/run_fogstack_local_demo.py",
        "--pack",
        "access",
        "--output-dir",
        str(output_dir),
    ], check=True)

    summary_path = output_dir / "fogstack-local-demo.summary.json"
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["kind"] == "FogStackLocalDemoRun"
    assert summary["bundle_id"] == "fogstack.access"
    assert summary["version"] == "0.1.0"
    assert summary["channel"] == "candidate"
    assert summary["support_state"] == "supported"

    expected_checks = {
        "bundle_verified",
        "validation_record_emitted",
        "publication_set_built",
        "promotion_policy_passed",
        "approval_record_checked",
        "approval_signature_verified",
        "publication_gate_passed",
        "registry_index_built",
        "filesystem_registry_published",
        "filesystem_registry_checked",
        "revocation_index_checked",
        "registry_root_checked",
    }
    assert expected_checks.issubset(set(summary["checks"]))

    artifacts = summary["artifacts"]
    required_artifacts = [
        "verify_json",
        "validation_record",
        "publication_set",
        "promoted_publication_set",
        "approval_record",
        "approval_signature_verification",
        "publication_gate",
        "registry_publication_index",
        "filesystem_release_pointer",
        "revocation_index",
        "registry_root_metadata",
    ]
    for key in required_artifacts:
        assert key in artifacts
        assert Path(artifacts[key]).exists(), f"missing {key}: {artifacts[key]}"

    gate = json.loads(Path(artifacts["publication_gate"]).read_text(encoding="utf-8"))
    assert gate["kind"] == "FogStackReleasePublicationGateRecord"
    assert gate["status"] == "pass"

    root = json.loads(Path(artifacts["registry_root_metadata"]).read_text(encoding="utf-8"))
    assert root["kind"] == "FogStackRegistryRootMetadata"
    assert root["signed"] is True
    assert root["releases"][0]["bundle_id"] == "fogstack.access"
    assert root["releases"][0]["release_pointer_digest"].startswith("sha256:")

    pointer = json.loads(Path(artifacts["filesystem_release_pointer"]).read_text(encoding="utf-8"))
    assert pointer["kind"] == "FogStackFilesystemRegistryReleasePointer"
    assert pointer["bundle_id"] == "fogstack.access"
    assert pointer["version"] == "0.1.0"
    assert pointer["index_digest"].startswith("sha256:")
