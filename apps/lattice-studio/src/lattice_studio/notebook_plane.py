"""Notebook surface plane for Lattice Studio.

Lattice Studio must not hard-code Jupyter as the notebook ontology. This module
models a notebook abstraction layer with adapters for JupyterLab, Apache
Zeppelin, Observable, Pluto.jl, and Quarto.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

NotebookAdapter = Literal["jupyterlab", "zeppelin", "observable", "plutojl", "quarto"]
NotebookRole = Literal["scientific-notebook", "collaborative-analytics", "reactive-visualization", "reactive-science", "technical-publishing"]


ADAPTER_ROLES: dict[NotebookAdapter, NotebookRole] = {
    "jupyterlab": "scientific-notebook",
    "zeppelin": "collaborative-analytics",
    "observable": "reactive-visualization",
    "plutojl": "reactive-science",
    "quarto": "technical-publishing",
}

ADAPTER_CAPABILITIES: dict[NotebookAdapter, list[str]] = {
    "jupyterlab": ["python", "r", "julia", "terminal", "kernel-spec", "general-purpose-notebook"],
    "zeppelin": ["spark", "sql", "scala", "python", "r", "collaborative-documents", "data-lake-analytics"],
    "observable": ["javascript", "sql", "html", "markdown", "reactive-visualization", "browser-native-storytelling"],
    "plutojl": ["julia", "reactive-cells", "scientific-computing", "dependency-aware-reexecution"],
    "quarto": ["python", "r", "julia", "observable", "markdown", "publishing", "slides", "books", "dashboards"],
}


@dataclass(frozen=True)
class NotebookSurfaceAdapter:
    adapter: NotebookAdapter
    role: NotebookRole
    capabilities: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "role": self.role,
            "capabilities": self.capabilities,
        }


@dataclass(frozen=True)
class NotebookSurfacePlane:
    plane_id: str
    default_adapter: NotebookAdapter
    adapters: list[NotebookSurfaceAdapter]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "NotebookSurfacePlane",
            "planeId": self.plane_id,
            "defaultAdapter": self.default_adapter,
            "adapters": [adapter.to_dict() for adapter in self.adapters],
            "createdAt": self.created_at,
            "designRule": "Notebook surfaces are adapter-based and must not hard-code Jupyter as the ontology.",
        }


@dataclass(frozen=True)
class NotebookSurfaceSpawnRequest:
    spawn_request_id: str
    adapter: NotebookAdapter
    role: NotebookRole
    notebook_session_id: str
    runtime_asset_id: str | None
    catalog_inputs: list[str]
    local_workspace_ref: str | None
    policy_ref: str | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "NotebookSurfaceSpawnRequest",
            "spawnRequestId": self.spawn_request_id,
            "adapter": self.adapter,
            "role": self.role,
            "notebookSessionId": self.notebook_session_id,
            "runtimeAssetId": self.runtime_asset_id,
            "catalogInputs": self.catalog_inputs,
            "localWorkspaceRef": self.local_workspace_ref,
            "policyRef": self.policy_ref,
            "createdAt": self.created_at,
            "capabilities": ADAPTER_CAPABILITIES[self.adapter],
        }


def demo_notebook_surface_plane() -> NotebookSurfacePlane:
    adapters = [
        NotebookSurfaceAdapter(adapter=adapter, role=ADAPTER_ROLES[adapter], capabilities=ADAPTER_CAPABILITIES[adapter])
        for adapter in ["jupyterlab", "zeppelin", "observable", "plutojl", "quarto"]
    ]
    return NotebookSurfacePlane(
        plane_id="notebook-plane:" + hashlib.sha256(b"lattice-studio-notebook-surface-plane").hexdigest()[:16],
        default_adapter="jupyterlab",
        adapters=adapters,
    )


def create_spawn_request(
    *,
    adapter: NotebookAdapter,
    notebook_session_id: str,
    runtime_asset_id: str | None,
    catalog_inputs: list[str] | None,
    local_workspace_ref: str | None,
    policy_ref: str | None,
) -> NotebookSurfaceSpawnRequest:
    seed = json.dumps(
        {
            "adapter": adapter,
            "notebookSessionId": notebook_session_id,
            "runtimeAssetId": runtime_asset_id,
            "catalogInputs": sorted(catalog_inputs or []),
            "localWorkspaceRef": local_workspace_ref,
            "policyRef": policy_ref,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return NotebookSurfaceSpawnRequest(
        spawn_request_id="notebook-spawn:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        adapter=adapter,
        role=ADAPTER_ROLES[adapter],
        notebook_session_id=notebook_session_id,
        runtime_asset_id=runtime_asset_id,
        catalog_inputs=sorted(catalog_inputs or []),
        local_workspace_ref=local_workspace_ref,
        policy_ref=policy_ref,
    )


def demo_spawn_requests() -> list[NotebookSurfaceSpawnRequest]:
    common = {
        "notebook_session_id": "notebook-session:demo1234567890abcd",
        "runtime_asset_id": "runtime-asset:prophet-python-ml:0.1.0",
        "catalog_inputs": [
            "catalog://datasets/demo-csv@0.1.0",
            "catalog://models/demo-classifier@0.1.0",
        ],
        "local_workspace_ref": "workspace://demo",
        "policy_ref": "policy://lattice-studio/demo",
    }
    return [create_spawn_request(adapter=adapter, **common) for adapter in ["jupyterlab", "zeppelin", "observable", "plutojl", "quarto"]]


def notebook_surface_evidence(plane: NotebookSurfacePlane, requests: list[NotebookSurfaceSpawnRequest]) -> dict[str, Any]:
    doc = {"plane": plane.to_dict(), "requests": [request.to_dict() for request in requests]}
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "NotebookSurfaceEvidence",
        "planeId": plane.plane_id,
        "surfaceDigest": f"sha256:{digest}",
        "adapterCount": len(plane.adapters),
        "spawnRequestCount": len(requests),
        "evidenceReports": [
            "adapter-plane",
            "jupyterlab-default",
            "zeppelin-collaborative-analytics",
            "observable-reactive-visualization",
            "plutojl-reactive-science",
            "quarto-reproducible-publishing",
            "runtime-binding",
            "catalog-input-binding",
            "policy-binding",
        ],
    }


def notebook_plane_to_platform_record(plane: NotebookSurfacePlane) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": plane.plane_id,
        "assetKind": "notebook-surface-plane",
        "name": "lattice-studio-notebook-surface-plane",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "NotebookSurfacePlane",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": None,
        "evidenceCorrelationId": plane.plane_id,
        "promotionChannel": "demo",
        "compatibilitySurfaces": [
            "lattice-studio",
            "jupyterlab",
            "zeppelin",
            "observable",
            "plutojl",
            "quarto",
            "datahub",
            "sourceos-local",
            "sherlock-search",
        ],
    }
