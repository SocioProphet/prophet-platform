#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS_PATH = ROOT / "apps/cell-service/src/cell_service/clickhouse_facts.py"
SERVICE_PATH = ROOT / "apps/cell-service/src/cell_service/service.py"
TEST_PATH = ROOT / "apps/cell-service/tests/test_clickhouse_facts.py"
CLICKHOUSE_SCHEMA_PATH = ROOT / "infra/datastores/clickhouse/cell/0001_personal_intelligence_cell_analytics.sql"

REQUIRED_TABLES = [
    "cell_signal_scores",
    "cell_feedback_outcomes",
    "cell_notification_metrics",
    "cell_watch_pattern_metrics",
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


def main() -> None:
    facts_text = require_file(FACTS_PATH)
    service_text = require_file(SERVICE_PATH)
    test_text = require_file(TEST_PATH)
    schema_text = require_file(CLICKHOUSE_SCHEMA_PATH)

    require_markers(
        facts_text,
        [
            "class CellFactSink",
            "class InMemoryCellFactSink",
            "class ClickHouseCellFactSink",
            "signal_score_fact",
            "feedback_outcome_fact",
            "notification_metric_fact",
            "watch_pattern_metric_fact",
            "INSERT INTO",
        ],
        "ClickHouse fact module",
    )
    require_markers(
        service_text,
        [
            "fact_sink",
            "InMemoryCellFactSink",
            "emit_signal_score",
            "emit_watch_pattern_metric",
            "emit_notification_metric",
            "emit_feedback_outcome",
            "analytics_snapshot",
        ],
        "cell service fact integration",
    )
    require_markers(
        test_text,
        [
            "test_signal_score_fact",
            "test_in_memory_fact_sink_records_loop_outputs",
            "test_clickhouse_fact_sink_executes_inserts",
            "FakeClickHouseConnection",
        ],
        "ClickHouse fact tests",
    )
    for table in REQUIRED_TABLES:
        if f"CREATE TABLE IF NOT EXISTS {table}" not in schema_text:
            fail(f"ClickHouse schema missing required emitted table: {table}")
        if table not in facts_text:
            fail(f"ClickHouse fact module missing table reference: {table}")

    print("OK: cell ClickHouse fact validation passed")


if __name__ == "__main__":
    main()
