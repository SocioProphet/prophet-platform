"""Crystal Atlas → DCAT / schema.org projection.

The first *real* external-interop emitter (prior surfaces emitted projection-shaped
JSON only). A Crystal Atlas asset-catalog-entry becomes a `dcat:Dataset` JSON-LD
document that CKAN (via ckanext-dcat), the DataHub Project, and CK.org can harvest.

The moat travels outward: standards-compliant DCAT/PROV metadata PLUS a Prophet
extension (`prophet:distributionClass`, `prophet:verifiedComputeRef`) that downstream
systems can ignore safely but that carries the governance/verification a plain catalog
cannot represent.
"""
from __future__ import annotations

from typing import Any

CONTEXT = {
    "dcat": "http://www.w3.org/ns/dcat#",
    "dct": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "schema": "https://schema.org/",
    "prophet": "https://schemas.socioprophet.org/ns#",
}

# distribution_class → DCAT-US access level.
_ACCESS = {
    "open": "public",
    "public_derived": "public",
    "free_tier_packaged": "public",
    "internal_private": "non-public",
    "premium_byo": "restricted",
    "premium_platform_managed": "restricted",
    "restricted_nonredistributable": "restricted",
}

# asset_kind → schema.org type (best-fit; dataset is the default).
_SCHEMA_TYPE = {
    "dataset": "schema:Dataset",
    "document": "schema:DigitalDocument",
    "conversation_thread": "schema:Conversation",
    "event_stream": "schema:DataFeed",
    "graph_bundle": "schema:Dataset",
    "evidence_bundle": "schema:Dataset",
    "agent_output_bundle": "schema:Dataset",
    "workflow_artifact": "schema:Dataset",
}


def access_rights(distribution_class: str | None) -> str:
    return _ACCESS.get(distribution_class or "", "restricted")


def asset_to_dcat(entry: dict[str, Any]) -> dict[str, Any]:
    """Map an asset-catalog-entry.v0 to a dcat:Dataset JSON-LD document."""
    asset_id = entry.get("asset_id")
    kind = entry.get("asset_kind")
    dist = entry.get("distribution_class")
    doc: dict[str, Any] = {
        "@context": CONTEXT,
        "@id": f"urn:prophet:asset:{asset_id}",
        "@type": ["dcat:Dataset", _SCHEMA_TYPE.get(kind, "schema:Dataset")],
        "dct:identifier": asset_id,
        "dct:type": kind,
        "dct:accessRights": access_rights(dist),
        "dct:publisher": {"@id": f"urn:prophet:tenant:{entry.get('tenant_id')}"},
        # source_refs are the lineage seed → PROV derivation.
        "prov:wasDerivedFrom": [{"@id": s} for s in (entry.get("source_refs") or [])],
        # Prophet extension — the governance the open standards can't carry.
        "prophet:distributionClass": dist,
        "prophet:tenant": entry.get("tenant_id"),
    }
    if entry.get("schema_ref"):
        doc["dct:conformsTo"] = entry["schema_ref"]
    if entry.get("created_at"):
        doc["dct:issued"] = entry["created_at"]
    if entry.get("updated_at"):
        doc["dct:modified"] = entry["updated_at"]
    fresh = entry.get("freshness")
    if isinstance(fresh, dict):
        doc["prophet:freshness"] = fresh
    return doc
