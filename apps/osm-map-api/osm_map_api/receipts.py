"""Response receipt helpers for OSM Map API.

Receipts make source, attribution, safety posture, and provenance visible to
callers. They are not cryptographic signatures yet; they are structured service
receipts that downstream gateways can sign later.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .receipt_digest import attach_digest

Receipt = dict[str, Any]
Artifact = dict[str, Any]


def _attribution_text(artifact: Artifact) -> str | None:
    attribution = artifact.get("attribution")
    if not isinstance(attribution, dict):
        return None
    value = attribution.get("attribution_text")
    return str(value) if value else None


def _license_refs(artifact: Artifact) -> list[str]:
    attribution = artifact.get("attribution")
    if not isinstance(attribution, dict):
        return []
    refs = attribution.get("license_refs")
    if isinstance(refs, list):
        return [str(ref) for ref in refs]
    ref = attribution.get("license_ref")
    return [str(ref)] if ref else []


def _source_refs(artifact: Artifact) -> list[str]:
    provenance = artifact.get("provenance")
    if isinstance(provenance, dict) and isinstance(provenance.get("source_refs"), list):
        return [str(ref) for ref in provenance["source_refs"]]
    refs = artifact.get("provenance_refs")
    if isinstance(refs, list):
        return [str(ref) for ref in refs]
    return []


def _route_safety_status(artifact: Artifact) -> str | None:
    value = artifact.get("safety_status")
    if value:
        return str(value)
    routing = artifact.get("routing")
    if isinstance(routing, dict) and routing.get("safety_status"):
        return str(routing["safety_status"])
    return None


def response_receipt(kind: str, artifacts: list[Artifact]) -> Receipt:
    """Create a receipt for one or more response artifacts."""

    source_refs: list[str] = []
    license_refs: list[str] = []
    attribution_texts: list[str] = []
    route_statuses: list[str] = []

    for artifact in artifacts:
        source_refs.extend(_source_refs(artifact))
        license_refs.extend(_license_refs(artifact))
        text = _attribution_text(artifact)
        if text:
            attribution_texts.append(text)
        status = _route_safety_status(artifact)
        if status:
            route_statuses.append(status)

    attribution_present = bool(attribution_texts and license_refs)
    safety_status = "advisory" if "advisory" in route_statuses else (route_statuses[0] if route_statuses else None)

    receipt = {
        "receipt_version": "v0",
        "service": "osm-map-api",
        "response_kind": kind,
        "source_refs": sorted(set(source_refs)),
        "provenance_refs_present": bool(source_refs),
        "attribution": {
            "required": True,
            "present": attribution_present,
            "texts": sorted(set(attribution_texts)),
            "license_refs": sorted(set(license_refs)),
        },
        "route_safety_status": safety_status,
        "safety_boundary": "OSM-derived routing is advisory unless separately validated.",
        "integrity": {
            "signed": False,
            "note": "Unsigned service receipt; gateway or release pipeline may add cryptographic attestation later.",
        },
    }
    return attach_digest(receipt)


def with_artifact_receipt(kind: str, artifact: Artifact) -> Artifact:
    """Return a copy of an artifact with an embedded receipt."""

    enriched = deepcopy(artifact)
    enriched["response_receipt"] = response_receipt(kind, [artifact])
    return enriched
