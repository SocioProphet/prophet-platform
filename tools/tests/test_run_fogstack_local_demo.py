from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED_CHECKS = {
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

CANONICAL_PACKS = ["access", "knowledge", "evaluation"]
CANONICAL_BUNDLES = {
    "fogstack.access",
    "fogstack.knowledge",
    "fogstack.evaluation",
}


def run_demo(pack: str, output_dir: Path) -> dict:
    subprocess.run(
        [
            sys.executable,
            "tools/run_fogstack_local_demo.py",
            "--pack",
            pack,
            "--output-dir",
            str(output_dir),
        ],
        check=True,
    )
    summary = output_dir / "fogstack-local-demo.summary.json"
    assert summary.exists()
    return json.loads(summary.read_text(encoding="utf-8"))


def assert_artifact(path_value: str) -> None:
    assert Path(path_value).exists(), f"missing artifact: {path_value}"


def assert_common(summary: dict, pack: str) -> dict:
    assert summary["kind"] == "FogStackLocalDemoRun"
    assert summary["pack"] == pack
    assert summary["version"] == "0.1.0"
    assert summary["channel"] == "candidate"
    assert summary["support_state"] == "supported"
    assert REQUIRED_CHECKS.issubset(set(summary["checks"]))

    artifacts = summary["artifacts"]
    for key in [
        "publication_set",
        "promoted_publication_set",
        "approval_record",
        "approval_signature_verification",
        "publication_gate",
        "registry_publication_index",
        "revocation_index",
        "registry_root_metadata",
    ]:
        assert key in artifacts
        assert_artifact(artifacts[key])

    gate = json.loads(Path(artifacts["publication_gate"]).read_text(encoding="utf-8"))
    assert gate["kind"] == "FogStackReleasePublicationGateRecord"
    assert gate["status"] == "pass"

    root = json.loads(Path(artifacts["registry_root_metadata"]).read_text(encoding="utf-8"))
    assert root["kind"] == "FogStackRegistryRootMetadata"
    assert root["signed"] is True
    return root


def test_run_fogstack_local_demo_access(tmp_path: Path) -> None:
    summary = run_demo("access", tmp_path / "access-demo")
    root = assert_common(summary, "access")

    assert summary["bundle_id"] == "fogstack.access"
    assert summary["packs"] == ["access"]
    assert len(summary["releases"]) == 1
    assert len(root["releases"]) == 1
    assert root["releases"][0]["bundle_id"] == "fogstack.access"

    for key in ["verify_json", "validation_record", "filesystem_release_pointer"]:
        assert key in summary["artifacts"]
        assert_artifact(summary["artifacts"][key])

    pointer = json.loads(Path(summary["artifacts"]["filesystem_release_pointer"]).read_text(encoding="utf-8"))
    assert pointer["kind"] == "FogStackFilesystemRegistryReleasePointer"
    assert pointer["bundle_id"] == "fogstack.access"
    assert pointer["version"] == "0.1.0"
    assert pointer["index_digest"].startswith("sha256:")


def test_run_fogstack_local_demo_all_packs(tmp_path: Path) -> None:
    summary = run_demo("all", tmp_path / "all-demo")
    root = assert_common(summary, "all")

    assert summary["bundle_id"] is None
    assert summary["packs"] == CANONICAL_PACKS
    assert len(summary["releases"]) == 3
    assert {item["bundle_id"] for item in summary["releases"]} == CANONICAL_BUNDLES
    assert {item["bundle_id"] for item in root["releases"]} == CANONICAL_BUNDLES

    for release in summary["releases"]:
        for key in ["verify_json", "validation_record", "filesystem_release_pointer"]:
            assert key in release
            assert_artifact(release[key])
        pointer = json.loads(Path(release["filesystem_release_pointer"]).read_text(encoding="utf-8"))
        assert pointer["bundle_id"] == release["bundle_id"]
        assert pointer["version"] == "0.1.0"


def test_run_fogstack_local_demo_summary_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "summary-demo"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_fogstack_local_demo.py",
            "--pack",
            "access",
            "--output-dir",
            str(output_dir),
            "--summary",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "FogStack local demo passed." in proc.stdout
    assert "Pack selection: access" in proc.stdout
    assert "Release count: 1" in proc.stdout
    assert "fogstack.access@0.1.0" in proc.stdout
    assert "Channel/support: candidate/supported" in proc.stdout
    assert "Publication gate:" in proc.stdout
    assert "Registry root metadata:" in proc.stdout
    assert "Summary JSON:" in proc.stdout
    assert "Checks passed: 12" in proc.stdout

    summary_path = output_dir / "fogstack-local-demo.summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["pack"] == "access"
    assert summary["bundle_id"] == "fogstack.access"
