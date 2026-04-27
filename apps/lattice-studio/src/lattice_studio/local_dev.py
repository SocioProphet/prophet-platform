"""SourceOS/SociOS local developer session model for Lattice Studio."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class LocalDevSession:
    local_session_id: str
    workspace_ref: str
    sourceos_ref: str
    notebook_endpoint: str
    terminal_endpoint: str
    browser_endpoint: str
    coding_agent_refs: list[str]
    atlas_context_ref: str | None
    paas_deployment_ref: str | None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "LocalDevSession",
            "localSessionId": self.local_session_id,
            "workspaceRef": self.workspace_ref,
            "sourceosRef": self.sourceos_ref,
            "notebookEndpoint": self.notebook_endpoint,
            "terminalEndpoint": self.terminal_endpoint,
            "browserEndpoint": self.browser_endpoint,
            "codingAgentRefs": self.coding_agent_refs,
            "atlasContextRef": self.atlas_context_ref,
            "paasDeploymentRef": self.paas_deployment_ref,
            "createdAt": self.created_at,
            "capabilities": [
                "local-notebook",
                "terminal",
                "browser-surface",
                "coding-agent-attach",
                "sourceos-runtime",
                "atlas-service-attach",
                "workflow-replay",
            ],
        }


def create_local_dev_session(*, workspace_ref: str, atlas_context_ref: str | None, paas_deployment_ref: str | None) -> LocalDevSession:
    seed = json.dumps(
        {"workspaceRef": workspace_ref, "atlasContextRef": atlas_context_ref, "paasDeploymentRef": paas_deployment_ref},
        sort_keys=True,
        separators=(",", ":"),
    )
    return LocalDevSession(
        local_session_id="local-dev-session:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        workspace_ref=workspace_ref,
        sourceos_ref="sourceos://local/workbench",
        notebook_endpoint="http://localhost:8888",
        terminal_endpoint="local://terminal/default",
        browser_endpoint="http://localhost:3000",
        coding_agent_refs=["agentplane://agents/coding-default", "openclaw://workflows/default"],
        atlas_context_ref=atlas_context_ref,
        paas_deployment_ref=paas_deployment_ref,
    )


def local_dev_to_platform_record(session: LocalDevSession) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": session.local_session_id,
        "assetKind": "local-dev-session",
        "name": session.workspace_ref,
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "LocalDevSession",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": None,
        "evidenceCorrelationId": session.local_session_id,
        "promotionChannel": "local-sourceos",
        "compatibilitySurfaces": [
            "sourceos-local",
            "socios-linux",
            "lattice-studio",
            "terminal",
            "browser",
            "coding-agent",
            "openclaw",
            "agentplane",
        ],
    }
