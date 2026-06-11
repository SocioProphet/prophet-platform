from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dead_letter import write_dead_letter
from .retry_policy import compute_next_retry_not_before, is_terminal_attempt, resolve_retry_policy
from .retry_state import (
    last_outcome_for_publication,
    next_attempt_for_publication,
    write_failure_evidence,
)
from .transport_adapters import dispatch_transport


def _home_fallback(suffix: str) -> Path:
    return Path.home() / suffix


def state_home() -> Path:
    value = os.environ.get("SOCIOPROFIT_STATE_HOME")
    if value:
        return Path(value)
    return _home_fallback(".local/state")


def platform_state_root() -> Path:
    return state_home() / "prophet-platform"


def transport_outbox_root(service: str = "zone-router") -> Path:
    return platform_state_root() / "transport-outbox" / service


def delivery_adapters_root(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "deliveries"


def outcome_records_root(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "records"


def outcome_log_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "outcome_log.jsonl"


def latest_outcome_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "latest.json"


def ensure_transport_dirs(service: str = "zone-router") -> None:
    outcome_records_root(service).mkdir(parents=True, exist_ok=True)
    delivery_adapters_root(service).mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_publication_record(path: str | Path) -> dict[str, Any]:
    record_path = Path(path).expanduser().resolve()
    return json.loads(record_path.read_text(encoding="utf-8"))


def write_publication_outcome(
    record: dict[str, Any],
    *,
    transport_ref: str = "transport://local/jsonl",
    service_ref: str = "apps/zone-router",
    service: str = "zone-router",
    status: str = "published",
    attempt: int = 1,
    transport_kind: str | None = None,
    delivery: dict[str, Any] | None = None,
    error: str | None = None,
    previous_outcome_ref: str | None = None,
    retry_eligible: bool | None = None,
    terminal: bool | None = None,
    next_retry_not_before: str | None = None,
    retry_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_transport_dirs(service)
    outcome_id = str(uuid.uuid4())
    created_at = _utc_now()
    outcome = {
        "version": "0.1",
        "outcome_id": outcome_id,
        "publication_id": record["publication_id"],
        "created_at": created_at,
        "service_ref": service_ref,
        "status": status,
        "transport_ref": transport_ref,
        "zone_ref": record["zone_ref"],
        "event_type": record["event_type"],
        "topic": record["topic"],
        "publication_mode": record["publication_mode"],
        "carrier_ref": record["carrier_ref"],
        "event_ref": record["event_ref"],
        "receipt_ref": record["receipt_ref"],
        "catalog_ref": record["catalog_ref"],
        "attempt": attempt,
    }
    if record.get("topic_ref"):
        outcome["topic_ref"] = record["topic_ref"]
    if transport_kind:
        outcome["transport_kind"] = transport_kind
    if previous_outcome_ref:
        outcome["previous_outcome_ref"] = previous_outcome_ref
    if retry_eligible is not None:
        outcome["retry_eligible"] = retry_eligible
    if terminal is not None:
        outcome["terminal"] = terminal
    if next_retry_not_before:
        outcome["next_retry_not_before"] = next_retry_not_before
    if retry_policy:
        outcome["max_attempts"] = int(retry_policy["max_attempts"])
        outcome["retry_backoff_seconds"] = int(retry_policy["retry_backoff_seconds"])
        outcome["retry_strategy"] = str(retry_policy["retry_strategy"])
    if status == "published":
        outcome["published_at"] = created_at
    if status == "failed":
        outcome["failed_at"] = created_at
    if error:
        outcome["error"] = error
    if delivery:
        if delivery.get("delivery_path"):
            outcome["delivery_ref"] = delivery["delivery_path"]
        if delivery.get("topic_log_path"):
            outcome["topic_log_ref"] = delivery["topic_log_path"]
        if delivery.get("delivery", {}).get("delivery_id"):
            outcome["delivery_id"] = delivery["delivery"]["delivery_id"]

    outcome_path = outcome_records_root(service) / f"{outcome_id}.outcome.json"
    outcome_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = outcome_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(outcome, sort_keys=True) + "\n")

    latest_path = latest_outcome_path(service)
    latest_path.write_text(json.dumps({"latest_outcome": outcome}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": status == "published",
        "outcome_path": str(outcome_path),
        "log_path": str(log_path),
        "latest_path": str(latest_path),
        "outcome": outcome,
    }


def publish_publication_record(
    record: dict[str, Any],
    *,
    transport_ref: str = "transport://local/jsonl",
    service_ref: str = "apps/zone-router",
    service: str = "zone-router",
    attempt: int | None = None,
) -> dict[str, Any]:
    ensure_transport_dirs(service)
    policy = resolve_retry_policy(record)
    previous_outcome = last_outcome_for_publication(record["publication_id"], service=service)
    resolved_attempt = attempt if attempt is not None else next_attempt_for_publication(record["publication_id"], service=service)
    previous_outcome_ref = previous_outcome.get("outcome_id") if previous_outcome else None

    transport_result = dispatch_transport(
        record,
        transport_ref=transport_ref,
        deliveries_root=delivery_adapters_root(service),
    )
    status = "published" if transport_result.get("ok") else "failed"

    if status == "published":
        retry_eligible = False
        terminal = True
        next_retry_not_before = None
    else:
        terminal = is_terminal_attempt(resolved_attempt, policy)
        retry_eligible = not terminal
        next_retry_not_before = compute_next_retry_not_before(resolved_attempt, policy)

    outcome_result = write_publication_outcome(
        record,
        transport_ref=transport_ref,
        service_ref=service_ref,
        service=service,
        status=status,
        attempt=resolved_attempt,
        transport_kind=transport_result.get("adapter"),
        delivery=transport_result if transport_result.get("ok") else None,
        error=transport_result.get("error"),
        previous_outcome_ref=previous_outcome_ref,
        retry_eligible=retry_eligible,
        terminal=terminal,
        next_retry_not_before=next_retry_not_before,
        retry_policy=policy,
    )

    if status == "failed":
        failure_evidence = write_failure_evidence(
            record,
            outcome_result["outcome"],
            service_ref=service_ref,
            service=service,
            previous_outcome_ref=previous_outcome_ref,
            retry_eligible=retry_eligible,
        )
        outcome_result["failure_evidence"] = failure_evidence
        if terminal and policy.get("dead_letter_on_terminal"):
            dead_letter = write_dead_letter(
                record,
                outcome_result["outcome"],
                policy,
                service_ref=service_ref,
                service=service,
                previous_outcome_ref=previous_outcome_ref,
            )
            outcome_result["dead_letter"] = dead_letter

    outcome_result["transport_result"] = transport_result
    return outcome_result
