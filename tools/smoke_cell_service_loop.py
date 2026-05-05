#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_SRC = ROOT / "apps/cell-service/src"
LOOP_CONTRACT = ROOT / "contracts/cell/personal-intelligence-cell.loop.v1.example.json"

sys.path.insert(0, str(APP_SRC))

from cell_service import CellService  # noqa: E402


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    if not LOOP_CONTRACT.exists():
        fail(f"missing loop contract: {LOOP_CONTRACT.relative_to(ROOT)}")

    loop = json.loads(LOOP_CONTRACT.read_text(encoding="utf-8"))
    service = CellService()
    health = service.health()
    if health.get("service") != "cell-service" or health.get("status") != "ok":
        fail("cell-service health check failed")
    if health.get("extraction") != "deterministic-template-v1":
        fail("cell-service deterministic extraction health marker missing")

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

    print("OK: cell-service loop smoke passed")


if __name__ == "__main__":
    main()
