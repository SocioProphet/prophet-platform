"""Catalog asset records for Lattice Studio.

The catalog model borrows the right primitives from Zenodo and CK/CMX:

- concept-level identity separate from immutable versions;
- version-specific persistent references;
- digest-bearing file records;
- portable automation/workflow metadata;
- first-class reproducibility command.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class CatalogFile:
    path: str
    digest: str
    media_type: str
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "digest": self.digest,
            "mediaType": self.media_type,
            "sizeBytes": self.size_bytes,
        }


@dataclass(frozen=True)
class CatalogAutomation:
    automation_id: str
    action: str
    reproduce_command: str
    workflow_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "automationId": self.automation_id,
            "action": self.action,
            "reproduceCommand": self.reproduce_command,
            "workflowRefs": self.workflow_refs,
        }


@dataclass(frozen=True)
class CatalogAssetVersion:
    catalog_asset_id: str
    version: str
    version_persistent_id: str | None
    files: list[CatalogFile]
    license: str
    access_policy: str
    automation: CatalogAutomation | None
    published_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "CatalogAssetVersion",
            "catalogAssetId": self.catalog_asset_id,
            "version": self.version,
            "versionPersistentId": self.version_persistent_id,
            "files": [file.to_dict() for file in self.files],
            "license": self.license,
            "accessPolicy": self.access_policy,
            "automation": self.automation.to_dict() if self.automation else None,
            "publishedAt": self.published_at,
            "immutableAfterPublication": True,
        }


@dataclass(frozen=True)
class CatalogAsset:
    catalog_asset_id: str
    title: str
    owner: str
    concept_persistent_id: str | None
    creators: list[str]
    collections: list[str]
    latest_version: CatalogAssetVersion

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "CatalogAsset",
            "catalogAssetId": self.catalog_asset_id,
            "title": self.title,
            "owner": self.owner,
            "conceptPersistentId": self.concept_persistent_id,
            "creators": self.creators,
            "collections": self.collections,
            "latestVersion": self.latest_version.to_dict(),
        }


def demo_catalog_asset() -> CatalogAsset:
    file = CatalogFile(
        path="demo-csv/data.csv",
        digest="sha256:" + hashlib.sha256(b"demo-csv-data").hexdigest(),
        media_type="text/csv",
        size_bytes=len(b"demo-csv-data"),
    )
    automation = CatalogAutomation(
        automation_id="automation://lattice-studio/load-demo-csv",
        action="load-csv",
        reproduce_command="lattice-studio create-session --catalog-input catalog://datasets/demo-csv@0.1.0",
        workflow_refs=["workflow://lattice-studio/demo-notebook"],
    )
    version = CatalogAssetVersion(
        catalog_asset_id="catalog://datasets/demo-csv",
        version="0.1.0",
        version_persistent_id="doi:10.0000/lattice.demo-csv.v1",
        files=[file],
        license="CC-BY-4.0",
        access_policy="public-metadata-restricted-files",
        automation=automation,
    )
    return CatalogAsset(
        catalog_asset_id="catalog://datasets/demo-csv",
        title="Demo CSV Dataset",
        owner="SocioProphet",
        concept_persistent_id="doi:10.0000/lattice.demo-csv",
        creators=["SocioProphet"],
        collections=["lattice-studio-demo"],
        latest_version=version,
    )


def catalog_evidence(asset: CatalogAsset) -> dict[str, Any]:
    doc = asset.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "CatalogAssetEvidence",
        "catalogAssetId": asset.catalog_asset_id,
        "latestVersion": asset.latest_version.version,
        "assetDigest": f"sha256:{digest}",
        "evidenceReports": [
            "concept-persistent-id",
            "version-persistent-id",
            "file-digests",
            "access-policy",
            "automation-reproduce-command",
        ],
    }
