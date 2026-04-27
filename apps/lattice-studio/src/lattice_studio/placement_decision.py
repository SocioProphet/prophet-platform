"""Placement and promotion dry-run decision reports for Lattice Studio.

This module answers the operational question: can this promoted notebook-derived
workload run on the requested BYOC/local placement path, without mutating the
host, cluster, or remote state?
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .byoc import demo_byoc_placement_plan
from .m2_topolvm import demo_m2_topolvm_placement_plan
from .notebook_launch import demo_launch_plans
from .notebook_promotion import demo_notebook_promotion_bundle

DecisionStatus = Literal["pass", "warn", "block"]


@dataclass(frozen=True)
class PlacementCheck:
    name: str
    status: DecisionStatus
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class PlacementDryRunReport:
    report_id: str
    status: DecisionStatus
    byoc_plan_ref: str
    m2_topolvm_plan_ref: str
    promotion_bundle_ref: str
    launch_plan_refs: list[str]
    checks: list[PlacementCheck]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "PlacementDryRunReport",
            "reportId": self.report_id,
            "status": self.status,
            "byocPlanRef": self.byoc_plan_ref,
            "m2TopoLVMPlanRef": self.m2_topolvm_plan_ref,
            "promotionBundleRef": self.promotion_bundle_ref,
            "launchPlanRefs": self.launch_plan_refs,
            "checks": [check.to_dict() for check in self.checks],
            "createdAt": self.created_at,
            "sideEffectBoundary": [
                "no-host-mutation",
                "no-kexec",
                "no-remote-state-mutation",
                "no-cluster-apply",
                "dry-run-only",
            ],
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def demo_placement_dry_run_report() -> PlacementDryRunReport:
    byoc = demo_byoc_placement_plan()
    m2 = demo_m2_topolvm_placement_plan()
    launch_plans = demo_launch_plans()
    promotion = demo_notebook_promotion_bundle()

    compute_kinds = {target.kind for target in byoc.compute_targets}
    storage_kinds = {profile.kind for profile in byoc.storage_profiles}
    io_kinds = {binding.kind for binding in byoc.io_bindings}
    promotion_targets = {candidate["target"] for candidate in promotion["promotionCandidates"]}
    launch_adapters = {plan.adapter for plan in launch_plans}

    checks = [
        PlacementCheck(
            name="byoc-compute-targets",
            status="pass" if {"kubernetes", "array-cluster", "local-sourceos"}.issubset(compute_kinds) else "block",
            detail="BYOC plan includes Kubernetes, Array cluster, and local SourceOS compute targets.",
        ),
        PlacementCheck(
            name="byoc-storage-targets",
            status="pass" if {"s3-compatible", "posix"}.issubset(storage_kinds) else "block",
            detail="BYOC plan includes object storage and local POSIX storage profiles.",
        ),
        PlacementCheck(
            name="byoc-io-bindings",
            status="pass" if {"object-store", "websocket-pty"}.issubset(io_kinds) else "block",
            detail="BYOC plan includes object-store and WebSocket PTY I/O lanes.",
        ),
        PlacementCheck(
            name="cloudshell-fog-terminal-path",
            status="pass" if byoc.cloudshell_fog.runtime_connector == "k8s-or-stub" else "warn",
            detail="CloudShell Fog can use Kubernetes or stub runtime connector for dry-run placement.",
        ),
        PlacementCheck(
            name="m2-topolvm-safety-boundary",
            status="pass" if "no-host-mutation" in m2.safety_boundary and "topolvm-mount-dry-run" in m2.safety_boundary else "block",
            detail="M2 TopoLVM placement remains proof-only and side-effect-free.",
        ),
        PlacementCheck(
            name="notebook-adapter-launch-coverage",
            status="pass" if {"jupyterlab", "zeppelin", "observable", "plutojl", "quarto"}.issubset(launch_adapters) else "block",
            detail="Launch plans cover JupyterLab, Zeppelin, Observable, Pluto.jl, and Quarto.",
        ),
        PlacementCheck(
            name="promotion-target-coverage",
            status="pass" if {"ray-train-job", "ray-serve-service", "beam-pipeline", "paas-service", "observable-app", "plutojl-job", "quarto-publication"}.issubset(promotion_targets) else "block",
            detail="Promotion bundle covers Ray Train, Ray Serve, Beam, PaaS, Observable, Pluto.jl, and Quarto targets.",
        ),
    ]
    status: DecisionStatus = "pass" if all(check.status == "pass" for check in checks) else "block"
    payload = {"byoc": byoc.plan_id, "m2": m2.plan_id, "checks": [check.name for check in checks]}
    return PlacementDryRunReport(
        report_id=_digest("placement-dry-run", payload),
        status=status,
        byoc_plan_ref=byoc.plan_id,
        m2_topolvm_plan_ref=m2.plan_id,
        promotion_bundle_ref="notebook-promotion-bundle:lattice-studio-demo",
        launch_plan_refs=[plan.launch_plan_id for plan in launch_plans],
        checks=checks,
    )


def placement_dry_run_evidence(report: PlacementDryRunReport) -> dict[str, Any]:
    doc = report.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "PlacementDryRunEvidence",
        "reportId": report.report_id,
        "reportDigest": f"sha256:{digest}",
        "status": report.status,
        "checkCount": len(report.checks),
        "evidenceReports": [
            "byoc-compute-storage-io",
            "cloudshell-fog-terminal-path",
            "m2-topolvm-safety-boundary",
            "notebook-adapter-launch-coverage",
            "promotion-target-coverage",
            "side-effect-boundary",
        ],
    }


def placement_dry_run_to_platform_record(report: PlacementDryRunReport) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": report.report_id,
        "assetKind": "placement-dry-run-report",
        "name": "lattice-studio-placement-dry-run-report",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "PlacementDryRunReport",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://placement/dry-run",
        "evidenceCorrelationId": report.report_id,
        "promotionChannel": report.status,
        "compatibilitySurfaces": [
            "lattice-studio",
            "byoc",
            "cloudshell-fog",
            "sourceos-m2",
            "topolvm",
            "notebook-launch",
            "notebook-promotion",
            "ray",
            "beam",
            "sherlock-search",
        ],
    }
