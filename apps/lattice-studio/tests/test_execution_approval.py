import json

from lattice_studio.execution_approval import (
    demo_execution_approval_request,
    execution_approval_evidence,
    execution_approval_to_platform_record,
)
from lattice_studio.execution_approval_cli import main


def test_execution_approval_request_is_request_only_and_policy_bound() -> None:
    request = demo_execution_approval_request()
    doc = request.to_dict()

    assert doc["kind"] == "ExecutionApprovalRequest"
    assert doc["status"] == "requested"
    assert doc["safeExecutionPlanRef"].startswith("safe-placement-execution:")
    assert doc["placementReportRef"] == "placement-dry-run:lattice-studio-demo"
    assert "request-artifact-only" in doc["boundary"]
    assert "no-apply" in doc["boundary"]
    assert "no-host-change" in doc["boundary"]
    assert "terminal-attach" in doc["blockedEffects"]
    assert "policy://placement/safe-execution" in doc["policyRefs"]
    assert len(doc["requiredApprovals"]) == 3


def test_execution_approval_evidence_and_platform_record() -> None:
    request = demo_execution_approval_request()
    evidence = execution_approval_evidence(request)
    record = execution_approval_to_platform_record(request)

    assert evidence["kind"] == "ExecutionApprovalEvidence"
    assert evidence["status"] == "requested"
    assert evidence["approvalCount"] == 3
    assert "required-approvals" in evidence["evidenceReports"]
    assert "blocked-effects" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "execution-approval-request"
    assert "approval-workflow" in record["compatibilitySurfaces"]
    assert "safe-placement-execution" in record["compatibilitySurfaces"]


def test_execution_approval_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "approval"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    request = json.loads((output_dir / "execution-approval-request.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "execution-approval-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "execution-approval-platform-record.json").read_text(encoding="utf-8"))

    assert request["kind"] == "ExecutionApprovalRequest"
    assert evidence["kind"] == "ExecutionApprovalEvidence"
    assert record["kind"] == "PlatformAssetRecord"
