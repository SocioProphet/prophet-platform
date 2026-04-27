"""Workspace source grounding flow for Lattice Studio.

This module turns office/workspace sources into a concrete Lattice Studio flow:
workspace sources -> source binding -> notebook session -> source-grounded
synthesis artifact -> publication receipt -> evidence/platform records.

The implementation is deterministic and fixture-backed for now. It is designed
so real workspace adapters can later replace fixture loading without changing the
object spine.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .session import NotebookSession, create_session, load_json

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_CONTRACTS = ROOT / "contracts" / "workspace"
RUNTIME_ASSET = ROOT / "apps" / "lattice-studio" / "examples" / "runtime-asset.prophet-python-ml.json"
WORKSPACE_SOURCE_FIXTURES = [
    "workspace-source.document.json",
    "workspace-source.sheet.json",
    "workspace-source.slide.json",
]


@dataclass(frozen=True)
class WorkspaceSourceBinding:
    binding_id: str
    project_id: str
    user_id: str
    notebook_session_id: str
    runtime_asset_id: str
    source_ids: list[str]
    policy_ref: str
    evidence_correlation_id: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "WorkspaceSourceBinding",
            "bindingId": self.binding_id,
            "projectId": self.project_id,
            "userId": self.user_id,
            "notebookSessionId": self.notebook_session_id,
            "runtimeAssetId": self.runtime_asset_id,
            "sourceIds": self.source_ids,
            "policyRef": self.policy_ref,
            "evidenceCorrelationId": self.evidence_correlation_id,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class WorkspaceSynthesisArtifact:
    artifact_id: str
    binding_id: str
    notebook_session_id: str
    runtime_asset_id: str
    source_ids: list[str]
    output_kind: str
    title: str
    claims: list[dict[str, Any]]
    policy_ref: str
    evidence_correlation_id: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "WorkspaceSynthesisArtifact",
            "artifactId": self.artifact_id,
            "bindingId": self.binding_id,
            "notebookSessionId": self.notebook_session_id,
            "runtimeAssetId": self.runtime_asset_id,
            "sourceIds": self.source_ids,
            "outputKind": self.output_kind,
            "title": self.title,
            "claims": self.claims,
            "policyRef": self.policy_ref,
            "evidenceCorrelationId": self.evidence_correlation_id,
            "createdAt": self.created_at,
        }


def demo_workspace_sources() -> list[dict[str, Any]]:
    return [load_json(WORKSPACE_CONTRACTS / fixture_name) for fixture_name in WORKSPACE_SOURCE_FIXTURES]


def create_workspace_session(
    *,
    project_id: str = "demo-project",
    user_id: str = "demo-user",
    policy_ref: str = "policy://workspace/demo",
) -> NotebookSession:
    runtime_asset = load_json(RUNTIME_ASSET)
    source_ids = [source["metadata"]["sourceId"] for source in demo_workspace_sources()]
    return create_session(
        project_id=project_id,
        user_id=user_id,
        runtime_asset=runtime_asset,
        catalog_inputs=source_ids,
        policy_ref=policy_ref,
    )


def create_workspace_source_binding(
    *,
    session: NotebookSession,
    sources: list[dict[str, Any]],
    policy_ref: str = "policy://workspace/demo",
) -> WorkspaceSourceBinding:
    source_ids = sorted(source["metadata"]["sourceId"] for source in sources)
    seed = _stable_json(
        {
            "projectId": session.project_id,
            "userId": session.user_id,
            "notebookSessionId": session.session_id,
            "runtimeAssetId": session.runtime_asset_id,
            "sourceIds": source_ids,
            "policyRef": policy_ref,
        }
    )
    binding_id = "workspace-binding:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return WorkspaceSourceBinding(
        binding_id=binding_id,
        project_id=session.project_id,
        user_id=session.user_id,
        notebook_session_id=session.session_id,
        runtime_asset_id=session.runtime_asset_id,
        source_ids=source_ids,
        policy_ref=policy_ref,
        evidence_correlation_id=binding_id,
    )


def create_workspace_synthesis_artifact(
    *,
    binding: WorkspaceSourceBinding,
    sources: list[dict[str, Any]],
) -> WorkspaceSynthesisArtifact:
    source_by_id = {source["metadata"]["sourceId"]: source for source in sources}
    claims = [
        {
            "claimId": "claim:source-set",
            "text": "The workspace source set contains a governed document, spreadsheet, and slide deck bound into one Lattice Studio session.",
            "sourceIds": binding.source_ids,
        },
        {
            "claimId": "claim:document-grounding",
            "text": "The document source provides narrative grounding for the generated report.",
            "sourceIds": ["workspace-source:docs/demo-brief"],
        },
        {
            "claimId": "claim:data-grounding",
            "text": "The spreadsheet source provides tabular/data grounding for analysis and charts.",
            "sourceIds": ["workspace-source:sheets/demo-dataset"],
        },
        {
            "claimId": "claim:presentation-grounding",
            "text": "The slide source provides publication and presentation context for the final artifact.",
            "sourceIds": ["workspace-source:slides/demo-report"],
        },
    ]
    for claim in claims:
        missing = sorted(set(claim["sourceIds"]) - set(source_by_id))
        if missing:
            raise ValueError(f"claim {claim['claimId']} references unknown source ids: {missing}")
    seed = _stable_json({"bindingId": binding.binding_id, "claims": claims})
    artifact_id = "workspace-synthesis:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return WorkspaceSynthesisArtifact(
        artifact_id=artifact_id,
        binding_id=binding.binding_id,
        notebook_session_id=binding.notebook_session_id,
        runtime_asset_id=binding.runtime_asset_id,
        source_ids=binding.source_ids,
        output_kind="source-grounded-brief",
        title="Demo workspace source-grounded report",
        claims=claims,
        policy_ref=binding.policy_ref,
        evidence_correlation_id=artifact_id,
    )


def synthesis_evidence(artifact: WorkspaceSynthesisArtifact) -> dict[str, Any]:
    doc = artifact.to_dict()
    digest = hashlib.sha256(_stable_json(doc).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "WorkspaceSynthesisEvidence",
        "artifactId": artifact.artifact_id,
        "bindingId": artifact.binding_id,
        "notebookSessionId": artifact.notebook_session_id,
        "runtimeAssetId": artifact.runtime_asset_id,
        "sourceIds": artifact.source_ids,
        "artifactDigest": f"sha256:{digest}",
        "evidenceReports": [
            "workspace-source-binding",
            "runtime-binding",
            "source-grounded-claims",
            "publication-ready-output",
        ],
    }


def create_workspace_publication_receipt(
    *,
    artifact: WorkspaceSynthesisArtifact,
    actor_id: str = "user:demo-user",
) -> dict[str, Any]:
    evidence = synthesis_evidence(artifact)
    return {
        "apiVersion": "workspace.socioprophet.dev/v1",
        "kind": "WorkspaceActionReceipt",
        "metadata": {
            "actionId": "workspace-action:publish/" + artifact.artifact_id.split(":", 1)[1],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "labels": {"surface": "docs", "source": "lattice-studio"},
        },
        "spec": {
            "actorId": actor_id,
            "surface": "docs",
            "actionType": "publish",
            "inputSourceIds": artifact.source_ids,
            "outputArtifactIds": [artifact.artifact_id],
            "runtimeAssetId": artifact.runtime_asset_id,
            "notebookSessionId": artifact.notebook_session_id,
            "policyRef": artifact.policy_ref,
            "evidenceCorrelationId": artifact.evidence_correlation_id,
            "outputDigest": evidence["artifactDigest"],
            "publicationRef": "workspace://docs/" + artifact.artifact_id,
            "shareScope": "project",
        },
    }


def demo_workspace_flow() -> dict[str, Any]:
    sources = demo_workspace_sources()
    session = create_workspace_session()
    binding = create_workspace_source_binding(session=session, sources=sources)
    synthesis = create_workspace_synthesis_artifact(binding=binding, sources=sources)
    receipt = create_workspace_publication_receipt(artifact=synthesis)
    return {
        "sources": sources,
        "session": session.to_dict(),
        "binding": binding.to_dict(),
        "synthesis": synthesis.to_dict(),
        "synthesisEvidence": synthesis_evidence(synthesis),
        "receipt": receipt,
    }


def write_workspace_flow_bundle(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    flow = demo_workspace_flow()
    written: list[Path] = []
    for source in flow["sources"]:
        source_id = source["metadata"]["sourceId"].replace("workspace-source:", "").replace("/", "_")
        path = output_dir / f"workspace-source.{source_id}.json"
        path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    for key, filename in [
        ("session", "notebook-session.json"),
        ("binding", "workspace-source-binding.json"),
        ("synthesis", "workspace-synthesis-artifact.json"),
        ("synthesisEvidence", "workspace-synthesis-evidence.json"),
        ("receipt", "workspace-action-receipt.publish-report.json"),
    ]:
        path = output_dir / filename
        path.write_text(json.dumps(flow[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
