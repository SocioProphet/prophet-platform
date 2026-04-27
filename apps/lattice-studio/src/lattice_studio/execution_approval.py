"""Governed approval request artifacts for Lattice Studio."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .safe_execution_plan import demo_safe_execution_plan

ApprovalRequestStatus = Literal["requested", "approved", "rejected", "expired"]
ApprovalScope = Literal["dry-run-render", "ephemeral-namespace", "readonly-mount", "terminal-session-render", "manifest-render"]


@dataclass(frozen=True)
class RequiredApproval:
    approver_ref: str
    scope: ApprovalScope
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "approverRef": self.approver_ref,
            "scope": self.scope,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExecutionApprovalRequest:
    request_id: str
    safe_execution_plan_ref: str
    placement_report_ref: str
    status: ApprovalRequestStatus
    requested_by: str
    required_approvals: list[RequiredApproval]
    policy_refs: list[str]
    evidence_refs: list[str]
    blocked_effects: list[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "ExecutionApprovalRequest",
            "requestId": self.request_id,
            "safeExecutionPlanRef": self.safe_execution_plan_ref,
            "placementReportRef": self.placement_report_ref,
            "status": self.status,
            "requestedBy": self.requested_by,
            "requiredApprovals": [approval.to_dict() for approval in self.required_approvals],
            "policyRefs": self.policy_refs,
            "evidenceRefs": self.evidence_refs,
            "blockedEffects": self.blocked_effects,
            "createdAt": self.created_at,
            "boundary": [
                "request-artifact-only",
                "no-apply",
                "no-host-change",
                "no-terminal-attach",
                "readonly-registry-only",
            ],
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def demo_execution_approval_request() -> ExecutionApprovalRequest:
    plan = demo_safe_execution_plan()
    approvals = [
        RequiredApproval(
            approver_ref="policy://approvers/platform-ops",
            scope="ephemeral-namespace",
            reason="Approve dry-run namespace preparation.",
        ),
        RequiredApproval(
            approver_ref="policy://approvers/sourceos-storage",
            scope="readonly-mount",
            reason="Approve readonly SourceOS registry mount planning.",
        ),
        RequiredApproval(
            approver_ref="policy://approvers/security-audit",
            scope="terminal-session-render",
            reason="Approve CloudShell Fog session request rendering.",
        ),
    ]
    payload = {"safePlan": plan.plan_id, "placement": plan.placement_report_ref, "approvals": len(approvals)}
    return ExecutionApprovalRequest(
        request_id=_digest("execution-approval", payload),
        safe_execution_plan_ref=plan.plan_id,
        placement_report_ref=plan.placement_report_ref,
        status="requested",
        requested_by="actor://lattice-studio/demo",
        required_approvals=approvals,
        policy_refs=[
            "policy://placement/safe-execution",
            "policy://byoc/notebook-shell-placement",
            "policy://sourceos/m2-topolvm-placement",
        ],
        evidence_refs=[
            f"evidence://{plan.plan_id}",
            "evidence://placement-dry-run:lattice-studio-demo",
        ],
        blocked_effects=[
            "host-change",
            "persistent-apply",
            "remote-state-change",
            "writeable-registry-mount",
            "terminal-attach",
        ],
    )


def execution_approval_evidence(request: ExecutionApprovalRequest) -> dict[str, Any]:
    doc = request.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ExecutionApprovalEvidence",
        "requestId": request.request_id,
        "requestDigest": f"sha256:{digest}",
        "status": request.status,
        "approvalCount": len(request.required_approvals),
        "evidenceReports": [
            "safe-execution-plan-binding",
            "placement-report-binding",
            "required-approvals",
            "policy-binding",
            "boundary",
            "blocked-effects",
        ],
    }


def execution_approval_to_platform_record(request: ExecutionApprovalRequest) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": request.request_id,
        "assetKind": "execution-approval-request",
        "name": "lattice-studio-execution-approval-request",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "ExecutionApprovalRequest",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://placement/safe-execution",
        "evidenceCorrelationId": request.request_id,
        "promotionChannel": request.status,
        "compatibilitySurfaces": [
            "lattice-studio",
            "safe-placement-execution",
            "placement-decision",
            "approval-workflow",
            "byoc",
            "cloudshell-fog",
            "sourceos-m2",
            "topolvm",
            "sherlock-search",
        ],
    }
