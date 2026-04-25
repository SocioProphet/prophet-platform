from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def failure_records_root(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "failures" / "records"


def failure_log_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "failure_log.jsonl"


def latest_failure_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "latest_failure.json"


def outcome_log_path(service: str = "zone-router") -> Path:
    return transport_outbox_root(service) / "outcome_log.jsonl"


def ensure_retry_dirs(service: str = "zone-router") -> None:
    failure_records_root(service).mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_outcomes_for_publication(publication_id: str, *, service: str = "zone-router") -> list[dict[str, Any]]:
    path = outcome_log_path(service)
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("publication_id") == publication_id:
            items.append(obj)
    return items


def last_outcome_for_publication(publication_id: str, *, service: str = "zone-router") -> dict[str, Any] | None:
    items = load_outcomes_for_publication(publication_id, service=service)
    return items[-1] if items else None


def next_attempt_for_publication(publication_id: str, *, service: str = "zone-router") -> int:
    items = load_outcomes_for_publication(publication_id, service=service)
    return len(items) + 1


def write_failure_evidence(
    record: dict[str, Any],
    outcome: dict[str, Any],
    *,
    service_ref: str = "apps/zone-router",
    service: str = "zone-router",
    classification: str = "transport-delivery",
    retry_eligible: bool = True,
    previous_outcome_ref: str | None = None,
) -> dict[str, Any]:
    ensure_retry_dirs(service)
    evidence_id = str(uuid.uuid4())
    evidence = {
        "version": "0.1",
        "evidence_id": evidence_id,
        "publication_id": record["publication_id"],
        "outcome_id": outcome["outcome_id"],
        "created_at": _utc_now(),
        "service_ref": service_ref,
        "classification": classification,
        "retry_eligible": retry_eligible,
        "attempt": outcome.get("attempt", 1),
        "transport_ref": outcome["transport_ref"],
        "error": outcome.get("error", "unknown transport failure"),
        "zone_ref": record["zone_ref"],
        "event_type": record["event_type"],
        "topic": record["topic"],
        "carrier_ref": record["carrier_ref"],
        "event_ref": record["event_ref"],
        "receipt_ref": record["receipt_ref"],
        "catalog_ref": record["catalog_ref"],
    }
    if previous_outcome_ref:
        evidence["previous_outcome_ref"] = previous_outcome_ref

    evidence_path = failure_records_root(service) / f"{evidence_id}.failure.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = failure_log_path(service)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(evidence, sort_keys=True) + "\n")

    latest_path = latest_failure_path(service)
    latest_path.write_text(json.dumps({"latest_failure": evidence}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "evidence_path": str(evidence_path),
        "log_path": str(log_path),
        "latest_path": str(latest_path),
        "evidence": evidence,
    }
