from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Protocol


class FactEmissionError(ValueError):
    """Raised when analytical fact emission cannot proceed."""


class ClickHouseConnectionLike(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any: ...


class CellFactSink(Protocol):
    def emit_signal_score(self, signal: dict[str, Any]) -> dict[str, Any]: ...
    def emit_feedback_outcome(self, feedback_event: dict[str, Any], signal: dict[str, Any]) -> dict[str, Any]: ...
    def emit_notification_metric(self, feed_item: dict[str, Any]) -> dict[str, Any]: ...
    def emit_watch_pattern_metric(self, signal: dict[str, Any]) -> dict[str, Any]: ...
    def snapshot(self) -> dict[str, list[dict[str, Any]]]: ...


class InMemoryCellFactSink:
    """In-memory analytical fact sink for tests, smoke, and local demos."""

    def __init__(self) -> None:
        self._facts: dict[str, list[dict[str, Any]]] = {
            "cell_signal_scores": [],
            "cell_feedback_outcomes": [],
            "cell_notification_metrics": [],
            "cell_watch_pattern_metrics": [],
        }

    def emit_signal_score(self, signal: dict[str, Any]) -> dict[str, Any]:
        fact = signal_score_fact(signal)
        self._facts["cell_signal_scores"].append(fact)
        return deepcopy(fact)

    def emit_feedback_outcome(self, feedback_event: dict[str, Any], signal: dict[str, Any]) -> dict[str, Any]:
        fact = feedback_outcome_fact(feedback_event, signal)
        self._facts["cell_feedback_outcomes"].append(fact)
        return deepcopy(fact)

    def emit_notification_metric(self, feed_item: dict[str, Any]) -> dict[str, Any]:
        fact = notification_metric_fact(feed_item)
        self._facts["cell_notification_metrics"].append(fact)
        return deepcopy(fact)

    def emit_watch_pattern_metric(self, signal: dict[str, Any]) -> dict[str, Any]:
        fact = watch_pattern_metric_fact(signal)
        self._facts["cell_watch_pattern_metrics"].append(fact)
        return deepcopy(fact)

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return deepcopy(self._facts)


class ClickHouseCellFactSink:
    """ClickHouse analytical fact sink for Personal Intelligence Cell runtime."""

    def __init__(self, connection: ClickHouseConnectionLike) -> None:
        self._connection = connection

    def emit_signal_score(self, signal: dict[str, Any]) -> dict[str, Any]:
        fact = signal_score_fact(signal)
        self._insert("cell_signal_scores", fact)
        return fact

    def emit_feedback_outcome(self, feedback_event: dict[str, Any], signal: dict[str, Any]) -> dict[str, Any]:
        fact = feedback_outcome_fact(feedback_event, signal)
        self._insert("cell_feedback_outcomes", fact)
        return fact

    def emit_notification_metric(self, feed_item: dict[str, Any]) -> dict[str, Any]:
        fact = notification_metric_fact(feed_item)
        self._insert("cell_notification_metrics", fact)
        return fact

    def emit_watch_pattern_metric(self, signal: dict[str, Any]) -> dict[str, Any]:
        fact = watch_pattern_metric_fact(signal)
        self._insert("cell_watch_pattern_metrics", fact)
        return fact

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return {}

    def _insert(self, table: str, fact: dict[str, Any]) -> None:
        columns = list(fact.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        column_sql = ", ".join(columns)
        sql = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
        self._connection.execute(sql, tuple(fact[column] for column in columns))


def signal_score_fact(signal: dict[str, Any]) -> dict[str, Any]:
    _require(signal, ["id", "cell_id", "source_id", "watch_id", "observed_at", "novelty_score", "relevance_score", "confidence_score", "policy_status"])
    return {
        "cell_id": signal["cell_id"],
        "signal_id": signal["id"],
        "source_id": signal["source_id"],
        "watch_id": signal["watch_id"],
        "observed_at": signal["observed_at"],
        "novelty_score": _score(signal["novelty_score"], "novelty_score"),
        "relevance_score": _score(signal["relevance_score"], "relevance_score"),
        "confidence_score": _score(signal["confidence_score"], "confidence_score"),
        "source_trust_score": _score(signal.get("source_trust_score", 0.5), "source_trust_score"),
        "policy_status": signal["policy_status"],
        "created_at": _now(),
    }


def feedback_outcome_fact(feedback_event: dict[str, Any], signal: dict[str, Any]) -> dict[str, Any]:
    _require(feedback_event, ["id", "cell_id", "signal_id", "actor_ref", "action", "created_at"])
    _require(signal, ["id", "source_id", "watch_id"])
    if feedback_event["signal_id"] != signal["id"]:
        raise FactEmissionError("feedback_event.signal_id must match signal.id")
    return {
        "cell_id": feedback_event["cell_id"],
        "signal_id": feedback_event["signal_id"],
        "source_id": signal["source_id"],
        "watch_id": signal["watch_id"],
        "actor_ref": feedback_event["actor_ref"],
        "action": feedback_event["action"],
        "event_at": feedback_event["created_at"],
    }


def notification_metric_fact(feed_item: dict[str, Any]) -> dict[str, Any]:
    _require(feed_item, ["id", "cell_id", "feed_kind", "created_at"])
    return {
        "cell_id": feed_item["cell_id"],
        "feed_kind": feed_item["feed_kind"],
        "event_at": feed_item["created_at"],
        "emitted_count": 1,
        "dismissed_count": 0,
        "saved_count": 0,
        "shared_count": 0,
    }


def watch_pattern_metric_fact(signal: dict[str, Any]) -> dict[str, Any]:
    _require(signal, ["id", "cell_id", "watch_id", "observed_at"])
    return {
        "cell_id": signal["cell_id"],
        "watch_id": signal["watch_id"],
        "pattern_id": signal.get("pattern_id", "watch-pattern://unknown"),
        "pattern_kind": signal.get("pattern_kind", "unknown"),
        "event_at": signal["observed_at"],
        "match_count": 1,
        "accepted_count": 0,
        "rejected_count": 0,
        "extraction_error_count": 0,
    }


def _require(obj: dict[str, Any], keys: list[str]) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise FactEmissionError(f"missing fact keys: {', '.join(missing)}")


def _score(value: Any, key: str) -> float:
    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise FactEmissionError(f"{key} must be numeric 0..1")
    return float(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
