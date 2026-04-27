import json

from lattice_studio.safe_execution_cli import main
from lattice_studio.safe_execution_plan import (
    demo_safe_execution_plan,
    safe_execution_evidence,
    safe_execution_to_platform_record,
)


def test_safe_execution_plan_preserves_side_effect_boundaries() -> None:
    plan = demo_safe_execution_plan()
    doc = plan.to_dict()

    assert doc["kind"] == "SafePlacementExecutionPlan"
    assert doc["approvalState"] == "not-requested"
    assert doc["placementReportRef"] == "placement-dry-run:lattice-studio-demo"
    assert "approval-required-before-cluster-apply" in doc["safetyBoundary"]
    assert "approval-required-before-host-mutation" in doc["safetyBoundary"]
    assert "readonly-m2-registry-mount-only" in doc["safetyBoundary"]
    assert "no-kexec" in doc["safetyBoundary"]

    by_kind = {step["kind"]: step for step in doc["steps"]}
    assert set(by_kind) == {
        "prepare-runtime",
        "mount-registry-readonly",
        "create-ephemeral-namespace",
        "prepare-terminal-session",
        "render-manifests",
        "emit-approval-request",
    }
    assert "writeable-m2-registry-mount" in by_kind["mount-registry-readonly"]["blockedSideEffects"]
    assert "persistent-cluster-apply" in by_kind["create-ephemeral-namespace"]["blockedSideEffects"]
    assert "render-session-request" in by_kind["prepare-terminal-session"]["allowedSideEffects"]


def test_safe_execution_evidence_and_platform_record() -> None:
    plan = demo_safe_execution_plan()
    evidence = safe_execution_evidence(plan)
    record = safe_execution_to_platform_record(plan)

    assert evidence["kind"] == "SafePlacementExecutionEvidence"
    assert evidence["approvalState"] == "not-requested"
    assert evidence["stepCount"] == 6
    assert "readonly-m2-registry-boundary" in evidence["evidenceReports"]
    assert "no-cluster-apply-before-approval" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "safe-placement-execution-plan"
    assert "safe-executor" in record["compatibilitySurfaces"]
    assert "placement-decision" in record["compatibilitySurfaces"]


def test_safe_execution_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "safe-execution"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    plan = json.loads((output_dir / "safe-placement-execution-plan.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "safe-placement-execution-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "safe-placement-execution-platform-record.json").read_text(encoding="utf-8"))

    assert plan["kind"] == "SafePlacementExecutionPlan"
    assert evidence["kind"] == "SafePlacementExecutionEvidence"
    assert record["kind"] == "PlatformAssetRecord"
