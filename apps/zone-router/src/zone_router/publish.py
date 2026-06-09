from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dead_letter import write_dead_letter
from .outbox import publication_outbox_root
from .retry_policy import (
    compute_next_retry_not_before,
    is_terminal_attempt,
    resolve_retry_policy,
)
from .retry_state import next_attempt_state
from .transport_adapters import deliver_publication_record


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _outcomes_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "outcomes"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _outcome_log_path(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service)
    root.mkdir(parents=True, exist_ok=True)
    return root / "publication_outcome_log.jsonl"


def load_publication_record(path: str | Path) -> dict[str, Any]:
    record_path = Path(path).expanduser().resolve()
    data = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected publication record object in {record_path}")
    return data


def _write_outcome(outcome: dict[str, Any], *, service: str) -> dict[str, Any]:
    outcome_path = _outcomes_root(service) / f"{outcome['outcome_id']}.publication-outcome.json"
    outcome["outcome_ref"] = str(outcome_path)
    outcome_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = _outcome_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(outcome, sort_keys=True) + "\n")

    return {"outcome_path": str(outcome_path), "log_path": str(log_path)}


def _attempt_fields(publication_id: str, *, service: str) -> dict[str, Any]:
    state = next_attempt_state(publication_id, service=service)
    return {
        "attempt": state["attempt"],
        "previous_outcome_id": state["previous_outcome_id"],
        "previous_outcome_status": state["previous_outcome_status"],
        "previous_outcome_ref": state["previous_outcome_ref"],
        "retry_after_failure": state["retry_after_failure"],
    }


def publish_publication_record(
    *,
    record_path: str | Path,
    transport_ref: str = "transport://local/jsonl",
    service: str = "zone-router",
) -> dict[str, Any]:
    path = Path(record_path).expanduser().resolve()
    record = load_publication_record(path)
    policy = resolve_retry_policy(record)
    attempt_fields = _attempt_fields(record["publication_id"], service=service)
    delivery_result = deliver_publication_record(
        record=record,
        publication_record_ref=str(path),
        transport_ref=transport_ref,
        service=service,
    )
    outcome_id = str(uuid.uuid4())

    if not delivery_result.get("ok"):
        failure = delivery_result["failure"]
        attempt = attempt_fields["attempt"]
        terminal = is_terminal_attempt(attempt, policy)
        retry_eligible_flag = not terminal
        next_retry_not_before = compute_next_retry_not_before(attempt, policy)
        outcome = {
            "version": "0.1",
            "outcome_id": outcome_id,
            "publication_id": record["publication_id"],
            "status": "failed",
            "zone_ref": record["zone_ref"],
            "topic": record["topic"],
            "transport_ref": transport_ref,
            "transport_kind": failure["transport_kind"],
            "failure_ref": delivery_result["failure_path"],
            "failure_id": failure["failure_id"],
            "publication_record_ref": str(path),
            "carrier_ref": record.get("carrier_ref"),
            "event_ref": record.get("event_ref"),
            "receipt_ref": record.get("receipt_ref"),
            "catalog_ref": record.get("catalog_ref"),
            "published_at": None,
            "failed_at": failure["failed_at"],
            "error": delivery_result["error"],
            "terminal": terminal,
            "next_retry_not_before": next_retry_not_before,
            "max_attempts": policy["max_attempts"],
            "retry_backoff_seconds": policy["retry_backoff_seconds"],
            "retry_strategy": policy["retry_strategy"],
            **attempt_fields,
        }
        outcome["retry_eligible"] = retry_eligible_flag
        refs = _write_outcome(outcome, service=service)
        result: dict[str, Any] = {
            "ok": False,
            "outcome_path": refs["outcome_path"],
            "log_path": refs["log_path"],
            "outcome": outcome,
            "failure": failure,
            "failure_path": delivery_result["failure_path"],
            "error": delivery_result["error"],
        }
        if terminal and policy.get("dead_letter_on_terminal", True):
            dead_letter_result = write_dead_letter(
                publication_id=record["publication_id"],
                outcome_id=outcome_id,
                outcome_ref=outcome.get("outcome_ref"),
                failure_id=failure.get("failure_id"),
                failure_ref=delivery_result.get("failure_path"),
                attempt=attempt,
                max_attempts=policy["max_attempts"],
                zone_ref=record["zone_ref"],
                topic=record["topic"],
                transport_ref=transport_ref,
                error=delivery_result.get("error"),
                service=service,
            )
            outcome["dead_letter_ref"] = dead_letter_result["dead_letter_ref"]
            result["dead_letter"] = dead_letter_result
        return result

    delivery = delivery_result["delivery"]
    outcome = {
        "version": "0.1",
        "outcome_id": outcome_id,
        "publication_id": record["publication_id"],
        "status": "published",
        "zone_ref": record["zone_ref"],
        "topic": record["topic"],
        "transport_ref": transport_ref,
        "transport_kind": delivery["transport_kind"],
        "delivery_ref": delivery_result["delivery_path"],
        "delivery_id": delivery["delivery_id"],
        "topic_log_ref": delivery_result["topic_log_path"],
        "publication_record_ref": str(path),
        "carrier_ref": record.get("carrier_ref"),
        "event_ref": record.get("event_ref"),
        "receipt_ref": record.get("receipt_ref"),
        "catalog_ref": record.get("catalog_ref"),
        "published_at": _utc_now(),
        "error": None,
        **attempt_fields,
    }
    outcome["retry_eligible"] = False
    refs = _write_outcome(outcome, service=service)

    return {
        "ok": True,
        "outcome_path": refs["outcome_path"],
        "log_path": refs["log_path"],
        "outcome": outcome,
        "delivery": delivery,
        "delivery_path": delivery_result["delivery_path"],
        "topic_log_path": delivery_result["topic_log_path"],
    }
