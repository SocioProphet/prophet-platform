"""Convert Lattice Studio outputs into PlatformAssetRecord objects.

This module bridges the Studio/catalog slice into the existing Lattice metadata
spine. Catalog assets and notebook sessions become the same canonical
PlatformAssetRecord identity shape used by runtime and boot product surfaces.
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
        "compatibilitySurfaces": ["lattice-studio", "jupyter", "prophet-platform", "sherlock-search", "slash-topics"],
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
