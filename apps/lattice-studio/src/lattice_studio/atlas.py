"""Atlas integration context for Lattice Studio.

Atlas provides TritRPC service scaffolds, model studies, Ray/Beam/Airflow lanes,
A2A envelopes, ontology/SHACL governance, observability, and Autopilot rollout
surfaces. This module makes those references explicit and side-effect-free.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AtlasContext:
    atlas_context_id: str
    atlas_service_ref: str
    atlas_study_refs: list[str]
    beam_pipeline_refs: list[str]
    airflow_dag_refs: list[str]
    ray_runner_ref: str | None
    a2a_envelope_ref: str | None
    ontology_ref: str | None
    shacl_constraint_ref: str | None
    observability_dashboard_ref: str | None
    autopilot_rollout_ref: str | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "AtlasContext",
            "atlasContextId": self.atlas_context_id,
            "atlasServiceRef": self.atlas_service_ref,
            "atlasStudyRefs": self.atlas_study_refs,
            "beamPipelineRefs": self.beam_pipeline_refs,
            "airflowDagRefs": self.airflow_dag_refs,
            "rayRunnerRef": self.ray_runner_ref,
            "a2aEnvelopeRef": self.a2a_envelope_ref,
            "ontologyRef": self.ontology_ref,
            "shaclConstraintRef": self.shacl_constraint_ref,
            "observabilityDashboardRef": self.observability_dashboard_ref,
            "autopilotRolloutRef": self.autopilot_rollout_ref,
            "createdAt": self.created_at,
            "sourceRepos": [
                "SocioProphet/atlas_master_bundle_complete",
                "SocioProphet/atlas_os_service_full",
                "SocioProphet/atlas_master_bundle_autopilot_fullorchestration",
            ],
        }


def demo_atlas_context() -> AtlasContext:
    seed = "atlas:lattice-studio:demo"
    return AtlasContext(
        atlas_context_id="atlas-context:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        atlas_service_ref="atlas://services/atlasd",
        atlas_study_refs=[
            "atlas://studies/gpt-chat-tune",
            "atlas://studies/yolo",
            "atlas://studies/rgcn",
        ],
        beam_pipeline_refs=["atlas://orchestration/beam/submit-intents"],
        airflow_dag_refs=["atlas://orchestration/airflow/demo-dag"],
        ray_runner_ref="atlas://os-service/ray-runner",
        a2a_envelope_ref="atlas://a2a/agent-envelope.avro",
        ontology_ref="atlas://ontology/context.jsonld",
        shacl_constraint_ref="atlas://ontology/constraints.shacl.ttl",
        observability_dashboard_ref="atlas://grafana/atlasd-observability",
        autopilot_rollout_ref="atlas://autopilot/promotion-rollout",
    )


def atlas_evidence(context: AtlasContext) -> dict[str, Any]:
    doc = context.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "AtlasContextEvidence",
        "atlasContextId": context.atlas_context_id,
        "contextDigest": f"sha256:{digest}",
        "evidenceReports": [
            "atlas-service-binding",
            "model-study-binding",
            "beam-airflow-workflow-binding",
            "ray-runner-binding",
            "a2a-envelope-binding",
            "ontology-shacl-binding",
            "observability-dashboard-binding",
            "autopilot-rollout-binding",
        ],
    }


def atlas_to_platform_record(context: AtlasContext) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": context.atlas_context_id,
        "assetKind": "atlas-context",
        "name": "lattice-studio-atlas-context",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "AtlasContext",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": None,
        "evidenceCorrelationId": context.atlas_context_id,
        "promotionChannel": "demo",
        "compatibilitySurfaces": [
            "lattice-studio",
            "atlas-service",
            "tritrpc",
            "ray",
            "beam",
            "airflow",
            "a2a",
            "sourceos-local",
            "agentplane",
        ],
    }
