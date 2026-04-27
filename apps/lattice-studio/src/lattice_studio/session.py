"""Governed notebook session records for Lattice Studio.

This is the first Watson Studio/JupyterHub-style vertical slice: a session is
bound to a project, a RuntimeAsset, optional catalog inputs, and an evidence
record. No notebook server is launched in this tranche; the model is designed so
JupyterHub/KubeSpawner/etc. can consume the same record later.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NotebookSession:
    session_id: str
    project_id: str
    user_id: str
    runtime_asset_id: str
    kernel_name: str
    catalog_inputs: list[str]
    policy_ref: str | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "NotebookSession",
            "sessionId": self.session_id,
            "projectId": self.project_id,
            "userId": self.user_id,
            "runtimeAssetId": self.runtime_asset_id,
            "kernelName": self.kernel_name,
            "catalogInputs": self.catalog_inputs,
            "policyRef": self.policy_ref,
            "createdAt": self.created_at,
        }


def create_session(
    *,
    project_id: str,
    user_id: str,
    runtime_asset: dict[str, Any],
    catalog_inputs: list[str] | None = None,
    policy_ref: str | None = None,
) -> NotebookSession:
    metadata = _required_dict(runtime_asset, "metadata")
    name = _required_str(metadata, "name")
    version = _required_str(metadata, "version")
    runtime_asset_id = f"runtime-asset:{name}:{version}"
    kernel_name = f"{name}-{version}"
    seed = json.dumps(
        {
            "projectId": project_id,
            "userId": user_id,
            "runtimeAssetId": runtime_asset_id,
            "catalogInputs": sorted(catalog_inputs or []),
            "policyRef": policy_ref,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    session_id = "notebook-session:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return NotebookSession(
        session_id=session_id,
        project_id=project_id,
        user_id=user_id,
        runtime_asset_id=runtime_asset_id,
        kernel_name=kernel_name,
        catalog_inputs=sorted(catalog_inputs or []),
        policy_ref=policy_ref,
    )


def evidence_for_session(session: NotebookSession) -> dict[str, Any]:
    session_doc = session.to_dict()
    digest = hashlib.sha256(json.dumps(session_doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "NotebookSessionEvidence",
        "sessionId": session.session_id,
        "runtimeAssetId": session.runtime_asset_id,
        "projectId": session.project_id,
        "userId": session.user_id,
        "sessionDigest": f"sha256:{digest}",
        "evidenceReports": [
            "runtime-binding",
            "kernel-selection",
            "catalog-input-binding",
            "policy-binding",
        ],
    }


def write_session_bundle(session: NotebookSession, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    session_path = output_dir / "notebook-session.json"
    evidence_path = output_dir / "notebook-session-evidence.json"
    session_path.write_text(json.dumps(session.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence_for_session(session), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [session_path, evidence_path]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value
