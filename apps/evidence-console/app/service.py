from __future__ import annotations

from datetime import datetime
from typing import Any

from . import client


def _parse_created_at(value: str | None) -> datetime:
    if not value:
        return datetime.min
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sorted(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: _parse_created_at(item.get("created_at")), reverse=True)


def _latest_match(items: list[dict[str, Any]], *, event_type: str | None = None, subject_ref: str | None = None) -> dict[str, Any] | None:
    for item in _sorted(items):
        if event_type is not None and item.get("event_type") != event_type:
            continue
        if subject_ref is not None and item.get("subject_ref") != subject_ref:
            continue
        return item
    return None


def _bundle_from_summary(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    return client.get_bundle(summary["service"], summary["correlation_id"])


def get_frontier_view(limit: int = 20) -> dict[str, Any]:
    items = client.get_recent_receipts("eval-fabric-api", limit=max(limit, 20))
    frontier = _bundle_from_summary(_latest_match(items, event_type="eval.fabric.frontier.read"))
    provenance = _bundle_from_summary(_latest_match(items, event_type="eval.fabric.frontier.provenance.read"))
    recent = _sorted([item for item in items if item.get("event_type") in {"eval.fabric.frontier.read", "eval.fabric.frontier.provenance.read"}])[:limit]
    return {
        "frontier": frontier,
        "provenance": provenance,
        "recent": recent,
    }


def get_model_view(model_release_id: str, limit: int = 30) -> dict[str, Any]:
    subject = f"model://{model_release_id}"
    items = client.get_recent_receipts("eval-fabric-api", limit=max(limit, 30))
    dossier = _bundle_from_summary(_latest_match(items, event_type="eval.fabric.dossier.read", subject_ref=subject))
    attribution = _bundle_from_summary(_latest_match(items, event_type="eval.fabric.attribution.read", subject_ref=subject))
    recent = _sorted([item for item in items if item.get("subject_ref") == subject])[:limit]
    return {
        "model_release_id": model_release_id,
        "dossier": dossier,
        "attribution": attribution,
        "recent": recent,
    }


def get_coverage_view(limit: int = 20) -> dict[str, Any]:
    items = client.get_recent_receipts("eval-fabric-api", limit=max(limit, 20))
    coverage = _bundle_from_summary(_latest_match(items, event_type="eval.fabric.competition.coverage.read"))
    radar = _bundle_from_summary(_latest_match(items, event_type="eval.fabric.radar.read"))
    recent = _sorted([item for item in items if item.get("event_type") in {"eval.fabric.competition.coverage.read", "eval.fabric.radar.read"}])[:limit]
    return {
        "coverage": coverage,
        "radar": radar,
        "recent": recent,
    }


def get_recent_events_view(limit: int = 25, per_service_limit: int = 15) -> dict[str, Any]:
    services = client.get_services()
    items: list[dict[str, Any]] = []
    for service_name in services:
        items.extend(client.get_recent_receipts(service_name, limit=per_service_limit))
    items = _sorted(items)[:limit]
    return {
        "services": services,
        "items": items,
    }
