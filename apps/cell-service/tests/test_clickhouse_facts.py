from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cell_service import CellService
from cell_service.clickhouse_facts import (
    ClickHouseCellFactSink,
    FactEmissionError,
    InMemoryCellFactSink,
    feedback_outcome_fact,
    notification_metric_fact,
    signal_score_fact,
    watch_pattern_metric_fact,
)

ROOT = Path(__file__).resolve().parents[3]
LOOP_CONTRACT = ROOT / "contracts/cell/personal-intelligence-cell.loop.v1.example.json"


def load_loop() -> dict:
    return json.loads(LOOP_CONTRACT.read_text(encoding="utf-8"))


class FakeClickHouseConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.calls.append((sql, params))


def test_signal_score_fact() -> None:
    signal = load_loop()["signal"]
    fact = signal_score_fact(signal)

    assert fact["cell_id"] == signal["cell_id"]
    assert fact["signal_id"] == signal["id"]
    assert fact["relevance_score"] == signal["relevance_score"]
    assert fact["policy_status"] == signal["policy_status"]


def test_feedback_notification_and_watch_pattern_facts() -> None:
    loop = load_loop()
    feedback = feedback_outcome_fact(loop["feedback_event"], loop["signal"])
    notification = notification_metric_fact(loop["feed_item"])
    watch_metric = watch_pattern_metric_fact(loop["signal"])

    assert feedback["action"] == "mark_relevant"
    assert feedback["source_id"] == loop["signal"]["source_id"]
    assert notification["emitted_count"] == 1
    assert notification["feed_kind"] == "private"
    assert watch_metric["match_count"] == 1
    assert watch_metric["watch_id"] == loop["signal"]["watch_id"]


def test_feedback_fact_rejects_mismatched_signal() -> None:
    loop = load_loop()
    bad_signal = dict(loop["signal"])
    bad_signal["id"] = "signal://different"

    with pytest.raises(FactEmissionError, match="must match"):
        feedback_outcome_fact(loop["feedback_event"], bad_signal)


def test_in_memory_fact_sink_records_loop_outputs() -> None:
    sink = InMemoryCellFactSink()
    service = CellService(fact_sink=sink)
    result = service.run_loop_contract(load_loop())
    facts = result["analytics"]

    assert len(facts["cell_signal_scores"]) == 1
    assert len(facts["cell_watch_pattern_metrics"]) == 1
    assert len(facts["cell_notification_metrics"]) == 1
    assert len(facts["cell_feedback_outcomes"]) == 1
    assert facts["cell_signal_scores"][0]["signal_id"] == result["signal"]["id"]


def test_clickhouse_fact_sink_executes_inserts() -> None:
    conn = FakeClickHouseConnection()
    sink = ClickHouseCellFactSink(conn)
    loop = load_loop()

    sink.emit_signal_score(loop["signal"])
    sink.emit_notification_metric(loop["feed_item"])
    sink.emit_feedback_outcome(loop["feedback_event"], loop["signal"])
    sink.emit_watch_pattern_metric(loop["signal"])

    sql = "\n".join(call[0] for call in conn.calls)
    assert "INSERT INTO cell_signal_scores" in sql
    assert "INSERT INTO cell_notification_metrics" in sql
    assert "INSERT INTO cell_feedback_outcomes" in sql
    assert "INSERT INTO cell_watch_pattern_metrics" in sql
    assert all(call[1] for call in conn.calls)
