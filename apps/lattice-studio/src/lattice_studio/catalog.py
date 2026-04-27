"""Catalog asset records for Lattice Studio.

The catalog model borrows the right primitives from MIT DataHub, Zenodo, and
CK/CMX:

- collaborative data/workbench objects;
- concept-level identity separate from immutable versions;
- version-specific persistent references;
- digest-bearing file records;
- portable automation/workflow metadata;
- first-class reproducibility commands;
- explicit asset classes for data, ML, applications, and services.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

CatalogAssetType = Literal["data", "ml-model", "application", "service", "workflow", "notebook"]


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
    runtime_asset_refs: list[str] = field(default_factory=list)
    dataset_refs: list[str] = field(default_factory=list)
    model_refs: list[str] = field(default_factory=list)
    service_refs: list[str] = field(default_factory=list)
    application_refs: list[str] = field(default_factory=list)
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
            "runtimeAssetRefs": self.runtime_asset_refs,
            "datasetRefs": self.dataset_refs,
            "modelRefs": self.model_refs,
            "serviceRefs": self.service_refs,
            "applicationRefs": self.application_refs,
            "publishedAt": self.published_at,
            "immutableAfterPublication": True,
        }


@dataclass(frozen=True)
class CatalogAsset:
    catalog_asset_id: str
    asset_type: CatalogAssetType
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
            "assetType": self.asset_type,
            "title": self.title,
            "owner": self.owner,
            "conceptPersistentId": self.concept_persistent_id,
            "creators": self.creators,
            "collections": self.collections,
            "latestVersion": self.latest_version.to_dict(),
        }


def _digest_for(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _file(path: str, media_type: str) -> CatalogFile:
    return CatalogFile(path=path, digest=_digest_for(path), media_type=media_type, size_bytes=len(path.encode("utf-8")))


def _automation(automation_id: str, action: str, command: str) -> CatalogAutomation:
    return CatalogAutomation(
        automation_id=automation_id,
        action=action,
        reproduce_command=command,
        workflow_refs=["workflow://lattice-studio/demo-vertical-slice"],
    )


def demo_catalog_asset() -> CatalogAsset:
    return demo_catalog_assets()[0]


def demo_catalog_assets() -> list[CatalogAsset]:
    data_version = CatalogAssetVersion(
        catalog_asset_id="catalog://datasets/demo-csv",
        version="0.1.0",
        version_persistent_id="doi:10.0000/lattice.demo-csv.v1",
        files=[_file("demo-csv/data.csv", "text/csv")],
        license="CC-BY-4.0",
        access_policy="public-metadata-restricted-files",
        automation=_automation(
            "automation://lattice-studio/load-demo-csv",
            "load-csv",
            "lattice-studio create-session --catalog-input catalog://datasets/demo-csv@0.1.0",
        ),
        runtime_asset_refs=["runtime-asset:prophet-python-ml:0.1.0"],
    )
    model_version = CatalogAssetVersion(
        catalog_asset_id="catalog://models/demo-classifier",
        version="0.1.0",
        version_persistent_id="doi:10.0000/lattice.demo-classifier.v1",
        files=[_file("demo-classifier/model.onnx", "application/octet-stream")],
        license="Apache-2.0",
        access_policy="governed-project-use",
        automation=_automation(
            "automation://lattice-studio/evaluate-demo-classifier",
            "evaluate-model",
            "lattice-studio create-session --catalog-input catalog://models/demo-classifier@0.1.0",
        ),
        runtime_asset_refs=["runtime-asset:prophet-python-ml:0.1.0"],
        dataset_refs=["catalog://datasets/demo-csv@0.1.0"],
    )
    app_version = CatalogAssetVersion(
        catalog_asset_id="catalog://applications/demo-notebook-app",
        version="0.1.0",
        version_persistent_id="doi:10.0000/lattice.demo-notebook-app.v1",
        files=[_file("demo-notebook-app/app.py", "text/x-python")],
        license="MIT",
        access_policy="project-members",
        automation=_automation(
            "automation://lattice-studio/run-demo-app",
            "run-application",
            "lattice-studio create-session --catalog-input catalog://applications/demo-notebook-app@0.1.0",
        ),
        dataset_refs=["catalog://datasets/demo-csv@0.1.0"],
        model_refs=["catalog://models/demo-classifier@0.1.0"],
    )
    service_version = CatalogAssetVersion(
        catalog_asset_id="catalog://services/demo-inference-service",
        version="0.1.0",
        version_persistent_id="doi:10.0000/lattice.demo-inference-service.v1",
        files=[_file("demo-inference-service/openapi.json", "application/json")],
        license="MIT",
        access_policy="service-account-scoped",
        automation=_automation(
            "automation://lattice-studio/smoke-demo-service",
            "smoke-service",
            "lattice-studio create-session --catalog-input catalog://services/demo-inference-service@0.1.0",
        ),
        model_refs=["catalog://models/demo-classifier@0.1.0"],
        application_refs=["catalog://applications/demo-notebook-app@0.1.0"],
    )
    return [
        CatalogAsset(
            catalog_asset_id="catalog://datasets/demo-csv",
            asset_type="data",
            title="Demo CSV Dataset",
            owner="SocioProphet",
            concept_persistent_id="doi:10.0000/lattice.demo-csv",
            creators=["SocioProphet"],
            collections=["lattice-studio-demo"],
            latest_version=data_version,
        ),
        CatalogAsset(
            catalog_asset_id="catalog://models/demo-classifier",
            asset_type="ml-model",
            title="Demo Classifier Model",
            owner="SocioProphet",
            concept_persistent_id="doi:10.0000/lattice.demo-classifier",
            creators=["SocioProphet"],
            collections=["lattice-studio-demo", "ml"],
            latest_version=model_version,
        ),
        CatalogAsset(
            catalog_asset_id="catalog://applications/demo-notebook-app",
            asset_type="application",
            title="Demo Notebook Application",
            owner="SocioProphet",
            concept_persistent_id="doi:10.0000/lattice.demo-notebook-app",
            creators=["SocioProphet"],
            collections=["lattice-studio-demo", "applications"],
            latest_version=app_version,
        ),
        CatalogAsset(
            catalog_asset_id="catalog://services/demo-inference-service",
            asset_type="service",
            title="Demo Inference Service",
            owner="SocioProphet",
            concept_persistent_id="doi:10.0000/lattice.demo-inference-service",
            creators=["SocioProphet"],
            collections=["lattice-studio-demo", "services"],
            latest_version=service_version,
        ),
    ]


def catalog_evidence(asset: CatalogAsset) -> dict[str, Any]:
    doc = asset.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "CatalogAssetEvidence",
        "catalogAssetId": asset.catalog_asset_id,
        "assetType": asset.asset_type,
        "latestVersion": asset.latest_version.version,
        "assetDigest": f"sha256:{digest}",
        "evidenceReports": [
            "concept-persistent-id",
            "version-persistent-id",
            "file-digests",
            "access-policy",
            "automation-reproduce-command",
            "linked-runtime-data-model-application-service-assets",
        ],
    }
