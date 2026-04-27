"""Dry-run launch plans for Lattice Studio notebook surface adapters.

The NotebookSurfacePlane defines adapter intent. This module turns spawn requests
into deterministic adapter-specific launch plans without starting external
services. Actual launch execution can later bind these plans to SourceOS,
Kubernetes, JupyterHub, Zeppelin, browser runtimes, Julia, or Quarto builders.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .notebook_plane import NotebookSurfaceSpawnRequest, demo_spawn_requests

LaunchBackend = Literal["jupyter-server", "zeppelin-server", "browser-runtime", "julia-process", "quarto-renderer"]

BACKENDS: dict[str, LaunchBackend] = {
    "jupyterlab": "jupyter-server",
    "zeppelin": "zeppelin-server",
    "observable": "browser-runtime",
    "plutojl": "julia-process",
    "quarto": "quarto-renderer",
}

COMMANDS: dict[str, list[str]] = {
    "jupyterlab": ["jupyter", "lab", "--ServerApp.token=<redacted>", "--ip=0.0.0.0"],
    "zeppelin": ["zeppelin-daemon.sh", "start", "--interpreter=spark,sql,python"],
    "observable": ["observable", "preview", "--workspace", "workspace://demo"],
    "plutojl": ["julia", "-e", "using Pluto; Pluto.run(host=\"0.0.0.0\")"],
    "quarto": ["quarto", "render", "notebooks/demo.qmd", "--to", "html"],
}


@dataclass(frozen=True)
class NotebookSurfaceLaunchPlan:
    launch_plan_id: str
    spawn_request_id: str
    adapter: str
    backend: LaunchBackend
    command: list[str]
    environment: dict[str, str]
    mounted_catalog_inputs: list[str]
    local_workspace_ref: str | None
    policy_ref: str | None
    dry_run: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "NotebookSurfaceLaunchPlan",
            "launchPlanId": self.launch_plan_id,
            "spawnRequestId": self.spawn_request_id,
            "adapter": self.adapter,
            "backend": self.backend,
            "command": self.command,
            "environment": self.environment,
            "mountedCatalogInputs": self.mounted_catalog_inputs,
            "localWorkspaceRef": self.local_workspace_ref,
            "policyRef": self.policy_ref,
            "dryRun": self.dry_run,
            "createdAt": self.created_at,
        }


def launch_plan_for_request(request: NotebookSurfaceSpawnRequest) -> NotebookSurfaceLaunchPlan:
    backend = BACKENDS[request.adapter]
    seed = json.dumps(
        {
            "spawnRequestId": request.spawn_request_id,
            "adapter": request.adapter,
            "backend": backend,
            "catalogInputs": request.catalog_inputs,
            "localWorkspaceRef": request.local_workspace_ref,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    environment = {
        "LATTICE_NOTEBOOK_ADAPTER": request.adapter,
        "LATTICE_NOTEBOOK_ROLE": request.role,
        "LATTICE_RUNTIME_ASSET_ID": request.runtime_asset_id or "",
        "LATTICE_POLICY_REF": request.policy_ref or "",
        "LATTICE_DRY_RUN": "true",
    }
    return NotebookSurfaceLaunchPlan(
        launch_plan_id="notebook-launch:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        spawn_request_id=request.spawn_request_id,
        adapter=request.adapter,
        backend=backend,
        command=COMMANDS[request.adapter],
        environment=environment,
        mounted_catalog_inputs=request.catalog_inputs,
        local_workspace_ref=request.local_workspace_ref,
        policy_ref=request.policy_ref,
    )


def demo_launch_plans() -> list[NotebookSurfaceLaunchPlan]:
    return [launch_plan_for_request(request) for request in demo_spawn_requests()]


def launch_plan_evidence(plans: list[NotebookSurfaceLaunchPlan]) -> dict[str, Any]:
    docs = [plan.to_dict() for plan in plans]
    digest = hashlib.sha256(json.dumps(docs, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "NotebookSurfaceLaunchEvidence",
        "launchPlanDigest": f"sha256:{digest}",
        "launchPlanCount": len(plans),
        "adapters": sorted({plan.adapter for plan in plans}),
        "backends": sorted({plan.backend for plan in plans}),
        "evidenceReports": [
            "adapter-specific-launch-plan",
            "dry-run-only",
            "runtime-environment-binding",
            "catalog-input-mount-binding",
            "local-workspace-binding",
            "policy-binding",
        ],
    }


def launch_plan_set_to_platform_record(plans: list[NotebookSurfaceLaunchPlan]) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": "notebook-launch-plan-set:lattice-studio-demo",
        "assetKind": "notebook-launch-plan-set",
        "name": "lattice-studio-notebook-launch-plans",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "NotebookSurfaceLaunchPlanSet",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://lattice-studio/demo",
        "evidenceCorrelationId": "notebook-launch-plan-set:lattice-studio-demo",
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "lattice-studio",
            "jupyterlab",
            "zeppelin",
            "observable",
            "plutojl",
            "quarto",
            "sourceos-local",
            "datahub",
            "sherlock-search",
        ],
    }
