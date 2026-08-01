#!/usr/bin/env python3
"""Connector roots (Workspace Control Plane, Phase 3 / D3, D4).

A root connector turns an external estate into governed assets + events against
the Phase-1 object model. Every root declares a rail (spec D4):

* **mirror** — produce indexed asset copies + events;
* **live**   — just-in-time: produce events only, no cached asset;
* **action** — side effects only (handled by workflow-run, not ingestion).

The local-files connector is fully implemented and credential-free. Cloud
connectors (Drive/OneDrive/Box/Apple) declare their delta+watch mechanism and
are gated behind credentials — their `sync` raises until wired, so the contract
is explicit without pretending to have access.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class RootConnector:
    """Base connector. `sync` returns (assets, events, new_cursor)."""

    provider = "base"

    def sync(self, root: dict[str, Any], since_cursor: Optional[str] = None):
        raise NotImplementedError

    def watch(self, root: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class LocalFilesConnector(RootConnector):
    """Fully-working connector over a local directory root."""

    provider = "local"

    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)

    def sync(self, root: dict[str, Any], since_cursor: Optional[str] = None):
        """Incrementally ingest files modified after `since_cursor` (an ISO mtime)."""
        rail = root.get("sync_mode", "mirror")
        if rail == "action":
            # The action rail performs side effects via workflow-run, not ingestion.
            return [], [], since_cursor

        since = datetime.fromisoformat(since_cursor) if since_cursor else None
        root_id = root.get("root_id", "root-local")
        assets: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        max_mtime = since

        for path in sorted(p for p in self.base_dir.rglob("*") if p.is_file()):
            st = path.stat()
            mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
            if since is not None and mtime <= since:
                continue  # incremental: skip unchanged
            if max_mtime is None or mtime > max_mtime:
                max_mtime = mtime

            rel = str(path.relative_to(self.base_dir))
            data = path.read_bytes()
            content_hash = f"sha256:{_sha256_hex(data)}"
            asset_id = f"asset://{root_id}/{rel}"
            version_id = content_hash[7:19]

            if rail == "mirror":
                assets.append({
                    "asset_id": asset_id,
                    "kind": "file",
                    "root_ref": root_id,
                    "current_version": {
                        "version_id": version_id,
                        "content_hash": content_hash,
                        "size_bytes": st.st_size,
                        "modified_at": _iso(st.st_mtime),
                    },
                    "prior_versions": [],
                    "created_at": _iso(st.st_ctime),
                })
            # Both mirror and live emit an event (live carries no cached asset copy).
            events.append({
                "event_id": f"evt-{_sha256_hex((asset_id + version_id).encode())[:12]}",
                "ts": datetime.now(timezone.utc).isoformat(),
                "case_id": f"root-sync/{root_id}",
                "activity": "AssetIngested",
                "actor": f"connector://{self.provider}",
                "object_refs": [asset_id],
                "inputs": {"root_ref": root_id, "rail": rail},
                "outputs": {"content_hash": content_hash},
                "prov": {"entity": asset_id, "activity": "AssetIngested", "agent": f"connector://{self.provider}"},
            })

        new_cursor = max_mtime.isoformat() if max_mtime is not None else since_cursor
        return assets, events, new_cursor


class _CredentialGatedCloudConnector(RootConnector):
    """Base for cloud connectors whose delta+watch requires OAuth credentials."""

    delta_mechanism = ""
    watch_mechanism = ""

    def sync(self, root: dict[str, Any], since_cursor: Optional[str] = None):
        raise NotImplementedError(
            f"{self.provider} sync requires OAuth credentials; delta mechanism: {self.delta_mechanism}"
        )

    def watch(self, root: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.provider} watch requires OAuth credentials; watch mechanism: {self.watch_mechanism}"
        )


class GoogleDriveConnector(_CredentialGatedCloudConnector):
    provider = "google"
    delta_mechanism = "changes.getStartPageToken + changes.list(pageToken)"
    watch_mechanism = "changes.watch (push channel)"


class OneDriveConnector(_CredentialGatedCloudConnector):
    provider = "microsoft"
    delta_mechanism = "driveItem delta / deltaLink (deleted facet for tombstones)"
    watch_mechanism = "Microsoft Graph change notifications (subscriptions)"


class BoxConnector(_CredentialGatedCloudConnector):
    provider = "box"
    delta_mechanism = "events endpoint / stream_position"
    watch_mechanism = "Box webhooks (file/folder events)"


class AppleICloudConnector(_CredentialGatedCloudConnector):
    provider = "apple"
    delta_mechanism = "NSMetadataQuery over ubiquitous documents scope"
    watch_mechanism = "NSMetadataQuery live updates + security-scoped bookmarks"


CLOUD_CONNECTORS = {
    "google": GoogleDriveConnector,
    "microsoft": OneDriveConnector,
    "box": BoxConnector,
    "apple": AppleICloudConnector,
}
