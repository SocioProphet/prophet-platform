#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_SRC = ROOT / "apps/cell-service/src"
LOOP_CONTRACT = ROOT / "contracts/cell/personal-intelligence-cell.loop.v1.example.json"
LAMPSTAND_FIXTURE = ROOT / "schemas/cell/lampstand-ingest-fixture.json"

sys.path.insert(0, str(APP_SRC))

from cell_service import CellService  # noqa: E402


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    if not LOOP_CONTRACT.exists():
        fail(f"missing loop contract: {LOOP_CONTRACT.relative_to(ROOT)}")
    if not LAMPSTAND_FIXTURE.exists():
        fail(f"missing Lampstand fixture: {LAMPSTAND_FIXTURE.relative_to(ROOT)}")

    loop = json.loads(LOOP_CONTRACT.read_text(encoding="utf-8"))
    service = CellService()
    health = service.health()
    if health.get("service") != "cell-service" or health.get("status") != "ok":
        fail("cell-service health check failed")
    if health.get("extraction") != "deterministic-template-v1":
        fail("cell-service deterministic extraction health marker missing")
    if health.get("feed") != "private-json+rss-v1":
        fail("cell-service feed health marker missing")
    if health.get("publication") != "slash-topics+new-hope+sherlock-v1":
        fail("cell-service publication health marker missing")
    if health.get("source_adapter") != "lampstand-v1":
        fail("cell-service Lampstand source adapter health marker missing")
    if health.get("facts") != "InMemoryCellFactSink":
        fail("cell-service fact sink health marker missing")

    result = service.run_loop_contract(loop)
    required_sections = [
        "cell",
        "cell_config",
        "source",
        "watch",
        "watch_pattern",
        "signal",
        "feed_item",
        "intent_event",
        "feedback_event",
        "cell_archive",
        "private_feed",
        "rss_feed",
        "publication_bundle",
        "analytics",
    ]
    for section in required_sections:
        if section not in result:
            fail(f"loop replay missing section: {section}")

    signal = result["signal"]
    if signal.get("relevance_score", 0) < 0.9:
        fail("loop replay signal relevance_score below expected threshold")
    if not signal.get("evidence_refs"):
        fail("loop replay signal missing evidence_refs")

    feed_item = result["feed_item"]
    if feed_item.get("policy_decision", {}).get("decision") != "allow":
        fail("loop replay feed item did not pass policy gate")

    intent = result["intent_event"]
    if signal["id"] not in intent.get("emitted_events", []):
        fail("loop replay intent event did not cite emitted signal")
    if feed_item["id"] not in intent.get("emitted_events", []):
        fail("loop replay intent event did not cite emitted feed item")

    archive = result["cell_archive"]
    if not archive.get("restore_dry_run_report_ref"):
        fail("loop replay archive missing restore dry-run report ref")

    private_feed = result["private_feed"]
    if private_feed.get("feed_kind") != "private" or private_feed.get("item_count") != 1:
        fail("private feed export did not include expected item")
    if "<rss version=\"2.0\"" not in result["rss_feed"]:
        fail("RSS export missing RSS 2.0 marker")

    bundle = result["publication_bundle"]
    if bundle.get("slashTopicSurface", {}).get("surfaceKind") != "slash-topic-cell-signal":
        fail("slash topic surface missing or invalid")
    if bundle.get("newHopeMembraneEvent", {}).get("membraneOutcome") != "admit":
        fail("New Hope membrane event missing admit outcome")
    if bundle.get("sherlockSearchPacket", {}).get("schemaVersion") != "v0.1":
        fail("Sherlock search packet missing schema version")

    analytics = result["analytics"]
    expected_tables = [
        "cell_signal_scores",
        "cell_watch_pattern_metrics",
        "cell_notification_metrics",
        "cell_feedback_outcomes",
    ]
    for table in expected_tables:
        if len(analytics.get(table, [])) != 1:
            fail(f"analytics table did not receive one fact: {table}")

    text_service = CellService()
    text_service.create_cell(loop["cell"])
    text_service.create_source(loop["source"])
    text_service.create_watch(loop["watch"])
    text_service.create_watch_pattern(loop["watch_pattern"])
    extracted_signal = text_service.ingest_text_signal(
        signal_id="signal://demo/smoke/text/001",
        cell_id=loop["cell"]["id"],
        source_id=loop["source"]["id"],
        watch_id=loop["watch"]["id"],
        text="SocioProphet/prophet-platform changed docs/PERSONAL_INTELLIGENCE_CELL_RUNTIME.md with new runtime design.",
    )
    expected = {
        "repo": "SocioProphet/prophet-platform",
        "path": "docs/PERSONAL_INTELLIGENCE_CELL_RUNTIME.md",
        "change_type": "new runtime design",
    }
    if extracted_signal.get("extractions") != expected:
        fail(f"deterministic extraction mismatch: {extracted_signal.get('extractions')}")
    if extracted_signal.get("confidence_score", 0) <= 0:
        fail("deterministic extraction confidence score missing")

    lampstand_fixture = json.loads(LAMPSTAND_FIXTURE.read_text(encoding="utf-8"))
    lampstand_service = CellService()
    lampstand_service.create_cell(lampstand_fixture["cell"])
    lampstand_service.create_watch(lampstand_fixture["watch"])
    lampstand_service.create_watch_pattern(lampstand_fixture["watch_pattern"])
    lampstand_signal = lampstand_service.ingest_lampstand_result(
        lampstand_fixture["lampstand_result"],
        cell_id=lampstand_fixture["cell"]["id"],
        watch_id=lampstand_fixture["watch"]["id"],
    )
    if lampstand_signal.get("id") != lampstand_fixture["expected"]["signal_id"]:
        fail("Lampstand adapter emitted unexpected signal id")
    if lampstand_signal.get("extractions", {}).get("carrier_ref") != lampstand_fixture["expected"]["carrier_ref"]:
        fail("Lampstand adapter extraction missing carrier ref")
    if len(lampstand_signal.get("evidence_refs", [])) < lampstand_fixture["expected"]["min_evidence_refs"]:
        fail("Lampstand adapter did not preserve enough evidence refs")

    print("OK: cell-service loop smoke passed")


if __name__ == "__main__":
    main()
