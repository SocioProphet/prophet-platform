"""Execution lineage records for Lattice Studio.

Assets are not enough. World-class catalog/workbench systems separate artifacts
from executions. This module records notebook, workflow, job, and service-run
executions with inputs, outputs, runtime, policy, and evidence bindings.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ExecutionKind = Literal["notebook-run", "workflow-run", "job-run", "service-run", "agent-run"]
ExecutionStatus = Literal["planned", "running", "succeeded", "failed", "blocked"]


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    execution_kind: ExecutionKind
    status: ExecutionStatus
    project_id: str
    runtime_asset_id: str | None
    notebook_session_id: str | None
    paas_deployment_id: str | None
    atlas_context_id: str | None
    input_asset_refs: list[str]
    output_asset_refs: list[str]
    policy_ref: str | None
    reproduce_command: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "ExecutionRecord",
            "executionId": self.execution_id,
            "executionKind": self.execution_kind,
            "status": self.status,
            "projectId": self.project_id,
            "runtimeAssetId": self.runtime_asset_id,
            "notebookSessionId": self.notebook_session_id,
            "paasDeploymentId": self.paas_deployment_id,
            "atlasContextId": self.atlas_context_id,
            "inputAssetRefs": self.input_asset_refs,
            "outputAssetRefs": self.output_asset_refs,
            "policyRef": self.policy_ref,
            "reproduceCommand": self.reproduce_command,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "lineagePredicates": [
                "used",
                "generated",
                "executedWithRuntime",
                "governedByPolicy",
                "producedEvidence",
            ],
        }


def create_execution_record(
    *,
    execution_kind: ExecutionKind,
    status: ExecutionStatus,
    project_id: str,
    runtime_asset_id: str | None,
    notebook_session_id: str | None,
    paas_deployment_id: str | None,
    atlas_context_id: str | None,
    input_asset_refs: list[str] | None,
    output_asset_refs: list[str] | None,
    policy_ref: str | None,
    reproduce_command: str,
) -> ExecutionRecord:
    seed = json.dumps(
        {
            "executionKind": execution_kind,
            "projectId": project_id,
            "runtimeAssetId": runtime_asset_id,
            "notebookSessionId": notebook_session_id,
            "paasDeploymentId": paas_deployment_id,
            "atlasContextId": atlas_context_id,
            "inputAssetRefs": sorted(input_asset_refs or []),
            "outputAssetRefs": sorted(output_asset_refs or []),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return ExecutionRecord(
        execution_id="execution:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        execution_kind=execution_kind,
        status=status,
        project_id=project_id,
        runtime_asset_id=runtime_asset_id,
        notebook_session_id=notebook_session_id,
        paas_deployment_id=paas_deployment_id,
        atlas_context_id=atlas_context_id,
        input_asset_refs=sorted(input_asset_refs or []),
        output_asset_refs=sorted(output_asset_refs or []),
        policy_ref=policy_ref,
        reproduce_command=reproduce_command,
        finished_at=datetime.now(timezone.utc).isoformat() if status in {"succeeded", "failed", "blocked"} else None,
    )


def demo_execution_record() -> ExecutionRecord:
    return create_execution_record(
        execution_kind="notebook-run",
        status="succeeded",
        project_id="demo-project",
        runtime_asset_id="runtime-asset:prophet-python-ml:0.1.0",
        notebook_session_id="notebook-session:demo1234567890abcd",
        paas_deployment_id="paas-deployment:demo1234567890",
        atlas_context_id="atlas-context:demo1234567890ab",
        input_asset_refs=[
            "catalog://datasets/demo-csv@0.1.0",
            "catalog://models/demo-classifier@0.1.0",
        ],
        output_asset_refs=[
            "catalog://services/demo-inference-service@0.1.0",
            "evidence://notebook-session/demo1234567890abcd",
        ],
        policy_ref="policy://lattice-studio/demo",
        reproduce_command="prophet lattice-studio create-session --project-id demo-project --catalog-input catalog://datasets/demo-csv@0.1.0",
    )


def execution_evidence(execution: ExecutionRecord) -> dict[str, Any]:
    doc = execution.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ExecutionEvidence",
        "executionId": execution.execution_id,
        "executionKind": execution.execution_kind,
        "status": execution.status,
        "executionDigest": f"sha256:{digest}",
        "evidenceReports": [
            "input-asset-binding",
            "output-asset-binding",
            "runtime-binding",
            "notebook-session-binding",
            "paas-deployment-binding",
            "atlas-context-binding",
            "policy-binding",
            "reproduce-command",
            "lineage-predicates",
        ],
    }


def execution_to_platform_record(execution: ExecutionRecord) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": execution.execution_id,
        "assetKind": f"execution-{execution.execution_kind}",
        "name": execution.execution_id,
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "ExecutionRecord",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": execution.policy_ref,
        "evidenceCorrelationId": execution.execution_id,
        "promotionChannel": execution.status,
        "compatibilitySurfaces": [
            "lattice-studio",
            "datahub",
            "execution-lineage",
            "sherlock-search",
            "slash-topics",
            "memory-mesh",
            "ontogenesis",
        ],
    }
