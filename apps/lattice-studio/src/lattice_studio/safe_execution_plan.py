"""Safe execution plans for Lattice Studio placement decisions.

A PlacementDryRunReport answers whether a workload can run here. This module
models the next controlled step: what a future executor is allowed to do, while
preserving side-effect boundaries until an explicit approval path exists.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ExecutionStepKind = Literal[
    "prepare-runtime",
    "mount-registry-readonly",
    "create-ephemeral-namespace",
    "prepare-terminal-session",
    "render-manifests",
    "emit-approval-request",
]
ApprovalState = Literal["not-requested", "requested", "approved", "rejected"]


@dataclass(frozen=True)
class SafeExecutionStep:
    step_id: str
    kind: ExecutionStepKind
    description: str
    allowed_side_effects: list[str]
    blocked_side_effects: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stepId": self.step_id,
            "kind": self.kind,
            "description": self.description,
            "allowedSideEffects": self.allowed_side_effects,
            "blockedSideEffects": self.blocked_side_effects,
        }


@dataclass(frozen=True)
class SafePlacementExecutionPlan:
    plan_id: str
    placement_report_ref: str
    approval_state: ApprovalState
    executor_ref: str
    target_refs: list[str]
    steps: list[SafeExecutionStep]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "SafePlacementExecutionPlan",
            "planId": self.plan_id,
            "placementReportRef": self.placement_report_ref,
            "approvalState": self.approval_state,
            "executorRef": self.executor_ref,
            "targetRefs": self.target_refs,
            "steps": [step.to_dict() for step in self.steps],
            "createdAt": self.created_at,
            "safetyBoundary": [
                "approval-required-before-cluster-apply",
                "approval-required-before-host-mutation",
                "readonly-m2-registry-mount-only",
                "ephemeral-namespace-only-before-approval",
                "no-kexec",
                "no-remote-state-mutation-without-approval",
            ],
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _step(kind: ExecutionStepKind, description: str, allowed: list[str]) -> SafeExecutionStep:
    payload = {"kind": kind, "description": description}
    blocked = [
        "host-boot-mutation",
        "kexec",
        "persistent-cluster-apply",
        "remote-state-mutation",
        "writeable-m2-registry-mount",
    ]
    return SafeExecutionStep(
        step_id=_digest("safe-step", payload),
        kind=kind,
        description=description,
        allowed_side_effects=allowed,
        blocked_side_effects=blocked,
    )


def demo_safe_execution_plan() -> SafePlacementExecutionPlan:
    steps = [
        _step(
            "prepare-runtime",
            "Resolve runtime, image, and environment references without starting workload execution.",
            ["read-runtime-metadata", "render-environment"],
        ),
        _step(
            "mount-registry-readonly",
            "Prepare readonly SourceOS M2 filesystem registry mount for proof artifact access.",
            ["readonly-local-mount-plan"],
        ),
        _step(
            "create-ephemeral-namespace",
            "Render an ephemeral Kubernetes namespace plan for dry-run validation only.",
            ["dry-run-namespace-render"],
        ),
        _step(
            "prepare-terminal-session",
            "Prepare CloudShell Fog session request without attaching a live PTY.",
            ["render-session-request"],
        ),
        _step(
            "render-manifests",
            "Render Ray, Beam, PaaS, notebook, and placement manifests without applying them.",
            ["render-manifest-files"],
        ),
        _step(
            "emit-approval-request",
            "Emit approval request for any future state-changing executor action.",
            ["write-approval-request-artifact"],
        ),
    ]
    payload = {"placementReportRef": "placement-dry-run:lattice-studio-demo", "steps": len(steps)}
    return SafePlacementExecutionPlan(
        plan_id=_digest("safe-placement-execution", payload),
        placement_report_ref="placement-dry-run:lattice-studio-demo",
        approval_state="not-requested",
        executor_ref="executor://lattice-studio/safe-placement-dry-run",
        target_refs=[
            "byoc-placement:demo",
            "m2-topolvm-placement:demo",
            "notebook-launch-plan-set:lattice-studio-demo",
            "notebook-promotion-bundle:lattice-studio-demo",
            "cloudshell-fog:demo",
        ],
        steps=steps,
    )


def safe_execution_evidence(plan: SafePlacementExecutionPlan) -> dict[str, Any]:
    doc = plan.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "SafePlacementExecutionEvidence",
        "planId": plan.plan_id,
        "planDigest": f"sha256:{digest}",
        "approvalState": plan.approval_state,
        "stepCount": len(plan.steps),
        "evidenceReports": [
            "placement-report-binding",
            "approval-gate-binding",
            "readonly-m2-registry-boundary",
            "cloudshell-fog-session-render-only",
            "manifest-render-only",
            "no-host-mutation",
            "no-cluster-apply-before-approval",
        ],
    }


def safe_execution_to_platform_record(plan: SafePlacementExecutionPlan) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": plan.plan_id,
        "assetKind": "safe-placement-execution-plan",
        "name": "lattice-studio-safe-placement-execution-plan",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "SafePlacementExecutionPlan",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://placement/safe-execution",
        "evidenceCorrelationId": plan.plan_id,
        "promotionChannel": plan.approval_state,
        "compatibilitySurfaces": [
            "lattice-studio",
            "placement-decision",
            "safe-executor",
            "byoc",
            "cloudshell-fog",
            "sourceos-m2",
            "topolvm",
            "ray",
            "beam",
            "sherlock-search",
        ],
    }
