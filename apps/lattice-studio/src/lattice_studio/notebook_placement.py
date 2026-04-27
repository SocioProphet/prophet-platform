"""Unified notebook and shell placement for Lattice Studio.

CloudShell Fog and notebook surfaces should share placement semantics: run close
to governed data when possible, fall back to trusted cloud placement when not,
respect OIDC identity, policy profiles, resource quotas, trust tier, audit, and
telemetry. This module also adds a command-line notebook lane based on
SourceOS-Linux/dnote.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .byoc import CloudShellFogBinding, demo_byoc_placement_plan
from .notebook_plane import NotebookSurfaceSpawnRequest, demo_spawn_requests


@dataclass(frozen=True)
class CommandLineNotebookBinding:
    binding_id: str
    repo_ref: str
    engine: str
    local_store_ref: str
    sync_ref: str | None
    commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bindingId": self.binding_id,
            "repoRef": self.repo_ref,
            "engine": self.engine,
            "localStoreRef": self.local_store_ref,
            "syncRef": self.sync_ref,
            "commands": self.commands,
            "capabilities": [
                "single-binary",
                "sqlite-local-store",
                "full-text-search",
                "self-hosted-sync",
                "terminal-native-notes",
                "sourceos-local-friendly",
            ],
        }


@dataclass(frozen=True)
class NotebookPlacementDecision:
    decision_id: str
    spawn_request_id: str
    adapter: str
    placement_mode: str
    compute_target_ref: str
    storage_profile_ref: str
    io_binding_refs: list[str]
    cloudshell_session_api_ref: str
    policy_profile: str
    trust_tier: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisionId": self.decision_id,
            "spawnRequestId": self.spawn_request_id,
            "adapter": self.adapter,
            "placementMode": self.placement_mode,
            "computeTargetRef": self.compute_target_ref,
            "storageProfileRef": self.storage_profile_ref,
            "ioBindingRefs": self.io_binding_refs,
            "cloudshellSessionApiRef": self.cloudshell_session_api_ref,
            "policyProfile": self.policy_profile,
            "trustTier": self.trust_tier,
        }


@dataclass(frozen=True)
class UnifiedNotebookShellPlacementPlan:
    plan_id: str
    cloudshell_fog: CloudShellFogBinding
    command_line_notebook: CommandLineNotebookBinding
    notebook_decisions: list[NotebookPlacementDecision]
    placement_signals: list[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "UnifiedNotebookShellPlacementPlan",
            "planId": self.plan_id,
            "cloudShellFog": self.cloudshell_fog.to_dict(),
            "commandLineNotebook": self.command_line_notebook.to_dict(),
            "notebookDecisions": [decision.to_dict() for decision in self.notebook_decisions],
            "placementSignals": self.placement_signals,
            "createdAt": self.created_at,
            "designRule": "Notebook placement and shell placement must share data-locality, policy, trust, audit, and runtime-connector semantics.",
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def demo_command_line_notebook_binding() -> CommandLineNotebookBinding:
    return CommandLineNotebookBinding(
        binding_id="command-notebook:dnote",
        repo_ref="SourceOS-Linux/dnote",
        engine="dnote",
        local_store_ref="sqlite://$HOME/.dnote/dnote.db",
        sync_ref="https://dnote.local/sourceos-sync",
        commands=[
            "dnote add <book> -c <content>",
            "dnote view <book>",
            "dnote find <query>",
            "dnote sync",
        ],
    )


def placement_decision_for_request(request: NotebookSurfaceSpawnRequest) -> NotebookPlacementDecision:
    byoc = demo_byoc_placement_plan()
    if request.adapter == "zeppelin":
        compute_ref = "compute:kubernetes-demo"
        storage_ref = "storage:s3-compatible-demo"
        trust_tier = "trusted-cloud-or-region"
    elif request.adapter in {"jupyterlab", "plutojl"}:
        compute_ref = "compute:array-demo"
        storage_ref = "storage:s3-compatible-demo"
        trust_tier = "customer-controlled-compute"
    else:
        compute_ref = "compute:sourceos-local-demo"
        storage_ref = "storage:posix-local-demo"
        trust_tier = "local-edge"
    io_refs = [binding.binding_id for binding in byoc.io_bindings]
    payload = {"spawnRequestId": request.spawn_request_id, "adapter": request.adapter, "compute": compute_ref}
    return NotebookPlacementDecision(
        decision_id=_digest("notebook-placement", payload),
        spawn_request_id=request.spawn_request_id,
        adapter=request.adapter,
        placement_mode="fog-first-cloud-fallback",
        compute_target_ref=compute_ref,
        storage_profile_ref=storage_ref,
        io_binding_refs=io_refs,
        cloudshell_session_api_ref="POST /v1/sessions",
        policy_profile="default",
        trust_tier=trust_tier,
    )


def demo_unified_notebook_shell_placement_plan() -> UnifiedNotebookShellPlacementPlan:
    byoc = demo_byoc_placement_plan()
    requests = demo_spawn_requests()
    decisions = [placement_decision_for_request(request) for request in requests]
    payload = {"cloudshell": byoc.cloudshell_fog.binding_id, "decisions": len(decisions)}
    return UnifiedNotebookShellPlacementPlan(
        plan_id=_digest("notebook-shell-placement", payload),
        cloudshell_fog=byoc.cloudshell_fog,
        command_line_notebook=demo_command_line_notebook_binding(),
        notebook_decisions=decisions,
        placement_signals=[
            "latency",
            "capacity",
            "trust-tier",
            "data-residency",
            "policy-profile",
            "runtime-connector",
            "audit-requirement",
            "telemetry-requirement",
        ],
    )


def notebook_shell_placement_evidence(plan: UnifiedNotebookShellPlacementPlan) -> dict[str, Any]:
    doc = plan.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "NotebookShellPlacementEvidence",
        "planId": plan.plan_id,
        "placementDigest": f"sha256:{digest}",
        "notebookDecisionCount": len(plan.notebook_decisions),
        "evidenceReports": [
            "shared-cloudshell-notebook-placement",
            "fog-first-cloud-fallback",
            "policy-profile-binding",
            "oidc-session-binding",
            "websocket-pty-binding",
            "command-line-notebook-binding",
            "dnote-sqlite-store",
            "audit-telemetry-binding",
        ],
    }


def notebook_shell_placement_to_platform_record(plan: UnifiedNotebookShellPlacementPlan) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": plan.plan_id,
        "assetKind": "notebook-shell-placement-plan",
        "name": "lattice-studio-notebook-shell-placement-plan",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "UnifiedNotebookShellPlacementPlan",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://byoc/notebook-shell-placement",
        "evidenceCorrelationId": plan.plan_id,
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "lattice-studio",
            "cloudshell-fog",
            "sourceos-local",
            "socios-linux",
            "dnote",
            "jupyterlab",
            "zeppelin",
            "observable",
            "plutojl",
            "quarto",
            "byoc",
            "websocket-pty",
            "sherlock-search",
        ],
    }
