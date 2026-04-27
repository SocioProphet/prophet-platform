"""Convert Lattice Studio outputs into PlatformAssetRecord objects.

This module bridges the Studio/catalog/workspace slice into the existing Lattice
metadata spine. Catalog assets, notebook sessions, workspace sources, workspace
source bindings, synthesis artifacts, and workspace action receipts become the
same canonical PlatformAssetRecord identity shape used by runtime and boot
product surfaces.
"""

from __future__ import annotations

from typing import Any


def catalog_asset_to_platform_record(asset_doc: dict[str, Any]) -> dict[str, Any]:
    if asset_doc.get("kind") != "CatalogAsset":
        raise ValueError("catalog asset document kind must be CatalogAsset")
    catalog_asset_id = _required_str(asset_doc, "catalogAssetId")
    asset_type = _required_str(asset_doc, "assetType")
    latest_version = _required_dict(asset_doc, "latestVersion")
    version = _required_str(latest_version, "version")
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": f"catalog-asset:{catalog_asset_id}@{version}",
        "assetKind": f"catalog-{asset_type}",
        "name": catalog_asset_id,
        "version": version,
        "sourceApiVersion": _required_str(asset_doc, "apiVersion"),
        "sourceKind": "CatalogAsset",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": latest_version.get("accessPolicy"),
        "evidenceCorrelationId": None,
        "promotionChannel": "catalog-demo",
        "compatibilitySurfaces": ["lattice-studio", "prophet-platform", "sherlock-search", "slash-topics"],
    }


def notebook_session_to_platform_record(session_doc: dict[str, Any]) -> dict[str, Any]:
    if session_doc.get("kind") != "NotebookSession":
        raise ValueError("session document kind must be NotebookSession")
    session_id = _required_str(session_doc, "sessionId")
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": session_id,
        "assetKind": "notebook-session",
        "name": session_id,
        "version": "0.1.0",
        "sourceApiVersion": _required_str(session_doc, "apiVersion"),
        "sourceKind": "NotebookSession",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": session_doc.get("policyRef"),
        "evidenceCorrelationId": session_id,
        "promotionChannel": "session-demo",
        "compatibilitySurfaces": ["lattice-studio", "jupyter", "jupyterlab", "prophet-platform", "sherlock-search", "slash-topics"],
    }


def workspace_source_to_platform_record(source_doc: dict[str, Any]) -> dict[str, Any]:
    if source_doc.get("kind") != "WorkspaceSource":
        raise ValueError("workspace source document kind must be WorkspaceSource")
    metadata = _required_dict(source_doc, "metadata")
    spec = _required_dict(source_doc, "spec")
    source_id = _required_str(metadata, "sourceId")
    surface = _required_str(spec, "surface")
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": source_id,
        "assetKind": f"workspace-{surface}",
        "name": _required_str(metadata, "name"),
        "version": spec.get("versionRef") or "0.1.0",
        "sourceApiVersion": _required_str(source_doc, "apiVersion"),
        "sourceKind": "WorkspaceSource",
        "producerRepo": "SocioProphet/prophet-workspace",
        "policyRef": spec.get("policyRef"),
        "evidenceCorrelationId": spec.get("evidenceCorrelationId"),
        "promotionChannel": "workspace-demo",
        "compatibilitySurfaces": [
            "lattice-studio",
            "prophet-workspace",
            "prophet-platform",
            "sherlock-search",
            "slash-topics",
            surface,
        ],
    }


def workspace_source_binding_to_platform_record(binding_doc: dict[str, Any]) -> dict[str, Any]:
    if binding_doc.get("kind") != "WorkspaceSourceBinding":
        raise ValueError("workspace binding document kind must be WorkspaceSourceBinding")
    binding_id = _required_str(binding_doc, "bindingId")
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": binding_id,
        "assetKind": "workspace-source-binding",
        "name": binding_id,
        "version": "0.1.0",
        "sourceApiVersion": _required_str(binding_doc, "apiVersion"),
        "sourceKind": "WorkspaceSourceBinding",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": binding_doc.get("policyRef"),
        "evidenceCorrelationId": binding_doc.get("evidenceCorrelationId"),
        "promotionChannel": "workspace-demo",
        "compatibilitySurfaces": [
            "lattice-studio",
            "prophet-workspace",
            "prophet-platform",
            "notebook-session",
            "workspace-source",
            "evidence-bundle",
        ],
    }


def workspace_synthesis_artifact_to_platform_record(artifact_doc: dict[str, Any]) -> dict[str, Any]:
    if artifact_doc.get("kind") != "WorkspaceSynthesisArtifact":
        raise ValueError("workspace synthesis document kind must be WorkspaceSynthesisArtifact")
    artifact_id = _required_str(artifact_doc, "artifactId")
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": artifact_id,
        "assetKind": "workspace-synthesis-artifact",
        "name": _required_str(artifact_doc, "title"),
        "version": "0.1.0",
        "sourceApiVersion": _required_str(artifact_doc, "apiVersion"),
        "sourceKind": "WorkspaceSynthesisArtifact",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": artifact_doc.get("policyRef"),
        "evidenceCorrelationId": artifact_doc.get("evidenceCorrelationId"),
        "promotionChannel": "workspace-demo",
        "compatibilitySurfaces": [
            "lattice-studio",
            "prophet-workspace",
            "prophet-platform",
            "source-grounded-synthesis",
            "workspace-publication",
            "evidence-bundle",
        ],
    }


def workspace_action_receipt_to_platform_record(receipt_doc: dict[str, Any]) -> dict[str, Any]:
    if receipt_doc.get("kind") != "WorkspaceActionReceipt":
        raise ValueError("workspace receipt document kind must be WorkspaceActionReceipt")
    metadata = _required_dict(receipt_doc, "metadata")
    spec = _required_dict(receipt_doc, "spec")
    action_id = _required_str(metadata, "actionId")
    surface = _required_str(spec, "surface")
    action_type = _required_str(spec, "actionType")
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": action_id,
        "assetKind": f"workspace-action-{action_type}",
        "name": action_id,
        "version": "0.1.0",
        "sourceApiVersion": _required_str(receipt_doc, "apiVersion"),
        "sourceKind": "WorkspaceActionReceipt",
        "producerRepo": "SocioProphet/prophet-workspace",
        "policyRef": spec.get("policyRef"),
        "evidenceCorrelationId": spec.get("evidenceCorrelationId"),
        "promotionChannel": "workspace-demo",
        "compatibilitySurfaces": [
            "lattice-studio",
            "prophet-workspace",
            "prophet-platform",
            "evidence-bundle",
            surface,
        ],
    }


def platform_record_set(records: list[dict[str, Any]]) -> dict[str, Any]:
    flattened: list[dict[str, Any]] = []
    for record in records:
        kind = record.get("kind")
        if kind == "PlatformAssetRecord":
            flattened.append(record)
            continue
        if kind == "PlatformAssetRecordSet":
            nested = record.get("records")
            if not isinstance(nested, list):
                raise ValueError("PlatformAssetRecordSet.records must be a list")
            for item in nested:
                if not isinstance(item, dict) or item.get("kind") != "PlatformAssetRecord":
                    raise ValueError("PlatformAssetRecordSet.records must contain PlatformAssetRecord objects")
                flattened.append(item)
            continue
        raise ValueError(f"unsupported platform record kind: {kind!r}")
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecordSet",
        "records": flattened,
    }


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
