#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "contracts/cell/cell-service.openapi.yaml"
ROUTES_PATH = ROOT / "contracts/cell/cell-service.routes.yaml"
RUNTIME_DOC_PATH = ROOT / "docs/PERSONAL_INTELLIGENCE_CELL_RUNTIME.md"
EVENT_TOPICS_PATH = ROOT / "docs/EVENT_BUS_TOPICS.md"
PUBLICATION_PATH = ROOT / "apps/cell-service/src/cell_service/publication.py"
SERVICE_PATH = ROOT / "apps/cell-service/src/cell_service/service.py"
SMOKE_PATH = ROOT / "tools/smoke_cell_service_loop.py"

REQUIRED_OPERATIONS = [
    "cell.health",
    "cell.create",
    "cell.list",
    "cell.get",
    "cell.config.put",
    "cell.config.get",
    "cell.source.create",
    "cell.watch.create",
    "cell.watchPattern.create",
    "cell.watchPattern.validate",
    "cell.signal.ingest",
    "cell.signal.ingestText",
    "cell.signal.ingestLampstand",
    "cell.feedItem.emit",
    "cell.feed.private.export",
    "cell.feed.rss.export",
    "cell.publication.bundle",
    "cell.feedback.record",
    "cell.archive.export",
    "cell.analytics.snapshot",
]

REQUIRED_POLICY_GATES = [
    "cell.create",
    "cell.configure",
    "source.create",
    "watch.create",
    "watch_pattern.create",
    "signal.ingest",
    "feed_item.emit",
    "feedback_event.record",
    "cell_archive.export",
]

REQUIRED_PATHS = [
    "/health",
    "/cells",
    "/cells/{cellId}",
    "/cells/{cellId}/config",
    "/sources",
    "/watches",
    "/watch-patterns",
    "/watch-patterns/validate",
    "/signals",
    "/signals/text",
    "/signals/lampstand",
    "/feed-items",
    "/cells/{cellId}/feeds/private",
    "/cells/{cellId}/feeds/rss",
    "/feed-items/{feedItemId}/publication-bundle",
    "/feedback-events",
    "/archives",
    "/cells/{cellId}/analytics",
]

REQUIRED_TOPICS = [
    "zone.cell.signal.ingested.v1",
    "zone.cell.signal.scored.v1",
    "zone.cell.feed.item_emitted.v1",
    "zone.cell.feed.private_exported.v1",
    "zone.cell.feed.rss_exported.v1",
    "zone.cell.slash_topic.surface_built.v1",
    "zone.cell.new_hope.membrane_event_built.v1",
    "zone.cell.sherlock.search_packet_built.v1",
    "zone.cell.feedback.recorded.v1",
    "zone.cell.archive.exported.v1",
]

REQUIRED_PUBLICATION_SURFACES = [
    "slashTopicSurface",
    "newHopeMembraneEvent",
    "sherlockSearchPacket",
]


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def require_file(path: Path) -> str:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8", errors="replace")


def require_markers(text: str, markers: list[str], where: str) -> None:
    for marker in markers:
        if marker not in text:
            fail(f"{where} missing marker: {marker}")


def validate_openapi(text: str) -> None:
    require_markers(
        text,
        [
            "openapi: 3.1.0",
            "title: SocioProphet Personal Intelligence Cell API",
            "url: /api/cell/v1",
            "bearerAuth",
            "TextSignalIngestRequest",
            "LampstandSignalIngestRequest",
            "PrivateFeedDocument",
            "PublicationBundle",
            "AnalyticsSnapshot",
        ],
        "OpenAPI contract",
    )
    for path in REQUIRED_PATHS:
        if path not in text:
            fail(f"OpenAPI contract missing path: {path}")
    for operation in REQUIRED_OPERATIONS:
        if f"operationId: {operation}" not in text:
            fail(f"OpenAPI contract missing operationId: {operation}")
    for gate in REQUIRED_POLICY_GATES:
        if f"x-policy-gate: {gate}" not in text:
            fail(f"OpenAPI contract missing x-policy-gate: {gate}")


def validate_routes(text: str) -> None:
    require_markers(
        text,
        [
            "base_path: /api/cell/v1",
            "openapi: contracts/cell/cell-service.openapi.yaml",
            "bearer_required: true",
            "evidence_refs_required_for_signal_ingest: true",
            "policy_decision_generated_by_service: true",
            "ungoverned_publication_allowed: false",
        ],
        "route manifest",
    )
    for operation in REQUIRED_OPERATIONS:
        if f"operation_id: {operation}" not in text:
            fail(f"route manifest missing operation_id: {operation}")
    for gate in REQUIRED_POLICY_GATES:
        if f"policy_gate: {gate}" not in text:
            fail(f"route manifest missing policy_gate: {gate}")
    for topic in REQUIRED_TOPICS:
        if topic not in text:
            fail(f"route manifest missing topic: {topic}")


def validate_route_operation_parity(openapi_text: str, routes_text: str) -> None:
    openapi_ops = set(re.findall(r"operationId:\s*([^\s]+)", openapi_text))
    route_ops = set(re.findall(r"operation_id:\s*([^\s]+)", routes_text))
    missing_in_routes = sorted(openapi_ops - route_ops)
    missing_in_openapi = sorted(route_ops - openapi_ops)
    if missing_in_routes:
        fail(f"operations missing in route manifest: {', '.join(missing_in_routes)}")
    if missing_in_openapi:
        fail(f"operations missing in OpenAPI contract: {', '.join(missing_in_openapi)}")


def validate_publication_traceability(publication_text: str, service_text: str, smoke_text: str, topics_text: str, runtime_doc: str) -> None:
    require_markers(
        publication_text,
        [
            "slash_topic_surface",
            "new_hope_membrane_event",
            "sherlock_search_packet",
            "cell_publication_bundle",
        ],
        "publication module",
    )
    service_delegates_bundle = "publication_bundle_for_feed_item" in service_text and "cell_publication_bundle" in service_text
    for surface in REQUIRED_PUBLICATION_SURFACES:
        if surface not in service_text and not service_delegates_bundle:
            fail(f"service missing publication surface: {surface}")
        if surface not in smoke_text:
            fail(f"smoke missing publication surface: {surface}")
    for topic in REQUIRED_TOPICS:
        if topic not in topics_text:
            fail(f"event topics doc missing topic: {topic}")
    require_markers(
        runtime_doc,
        [
            "PrivateFeed.Export",
            "RssFeed.Export",
            "PublicationBundle.Build",
            "SlashTopicSurface.Build",
            "NewHopeMembraneEvent.Build",
            "SherlockSearchPacket.Build",
        ],
        "runtime doc API section",
    )


def main() -> None:
    openapi_text = require_file(OPENAPI_PATH)
    routes_text = require_file(ROUTES_PATH)
    runtime_doc = require_file(RUNTIME_DOC_PATH)
    topics_text = require_file(EVENT_TOPICS_PATH)
    publication_text = require_file(PUBLICATION_PATH)
    service_text = require_file(SERVICE_PATH)
    smoke_text = require_file(SMOKE_PATH)

    validate_openapi(openapi_text)
    validate_routes(routes_text)
    validate_route_operation_parity(openapi_text, routes_text)
    validate_publication_traceability(publication_text, service_text, smoke_text, topics_text, runtime_doc)
    print("OK: cell gateway API validation passed")


if __name__ == "__main__":
    main()
