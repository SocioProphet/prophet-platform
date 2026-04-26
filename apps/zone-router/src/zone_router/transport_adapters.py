from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .outbox import publication_outbox_root

LOCAL_JSONL = "transport://local/jsonl"
KAFKA_JSONL = "transport://kafka/jsonl"
KAFKA_REMOTE = "transport://kafka/remote"
FAIL_TEST = "transport://fail/test"
SUPPORTED_TRANSPORTS = {LOCAL_JSONL, KAFKA_JSONL, KAFKA_REMOTE, FAIL_TEST}
REQUIRED_KAFKA_ENV = ("ZONE_ROUTER_KAFKA_BOOTSTRAP_SERVERS", "ZONE_ROUTER_KAFKA_TOPIC_PREFIX")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _transport_kind(transport_ref: str) -> str:
    if transport_ref == LOCAL_JSONL:
        return "local-jsonl"
    if transport_ref == KAFKA_JSONL:
        return "kafka-jsonl-local-standin"
    if transport_ref == KAFKA_REMOTE:
        return "kafka-remote"
    if transport_ref == FAIL_TEST:
        return "fail-test"
    return "unsupported"


def _deliveries_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "deliveries"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _failures_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "failures"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _topic_logs_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "topic-logs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_topic(topic: str) -> str:
    return topic.replace("/", "_").replace(":", "_")


def _failure_evidence(
    *,
    record: dict[str, Any],
    publication_record_ref: str,
    transport_ref: str,
    error: str,
    service: str,
) -> dict[str, Any]:
    failure_id = str(uuid.uuid4())
    failure = {
        "version": "0.1",
        "failure_id": failure_id,
        "publication_id": record["publication_id"],
        "transport_ref": transport_ref,
        "transport_kind": _transport_kind(transport_ref),
        "topic": record["topic"],
        "publication_record_ref": publication_record_ref,
        "carrier_ref": record.get("carrier_ref"),
        "event_ref": record.get("event_ref"),
        "receipt_ref": record.get("receipt_ref"),
        "catalog_ref": record.get("catalog_ref"),
        "failed_at": _utc_now(),
        "error": error,
    }
    failure_path = _failures_root(service) / f"{failure_id}.failure-evidence.json"
    failure_path.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": False, "failure_path": str(failure_path), "failure": failure, "error": error}


def _missing_remote_kafka_config() -> list[str]:
    return [name for name in REQUIRED_KAFKA_ENV if not os.environ.get(name)]


def _delivery_payload(
    *,
    record: dict[str, Any],
    publication_record_ref: str,
    transport_ref: str,
) -> dict[str, Any]:
    return {
        "version": "0.1",
        "delivery_id": str(uuid.uuid4()),
        "publication_id": record["publication_id"],
        "transport_ref": transport_ref,
        "transport_kind": _transport_kind(transport_ref),
        "topic": record["topic"],
        "publication_record_ref": publication_record_ref,
        "carrier_ref": record.get("carrier_ref"),
        "event_ref": record.get("event_ref"),
        "receipt_ref": record.get("receipt_ref"),
        "catalog_ref": record.get("catalog_ref"),
        "delivered_at": _utc_now(),
    }


def _write_local_delivery(*, record: dict[str, Any], publication_record_ref: str, transport_ref: str, service: str) -> dict[str, Any]:
    delivery = _delivery_payload(record=record, publication_record_ref=publication_record_ref, transport_ref=transport_ref)
    delivery_path = _deliveries_root(service) / f"{delivery['delivery_id']}.delivery.json"
    delivery_path.write_text(json.dumps(delivery, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    topic_log_path = _topic_logs_root(service) / f"{_safe_topic(record['topic'])}.jsonl"
    with topic_log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(delivery, sort_keys=True) + "\n")

    return {
        "ok": True,
        "delivery_path": str(delivery_path),
        "topic_log_path": str(topic_log_path),
        "delivery": delivery,
    }


def deliver_publication_record(
    *,
    record: dict[str, Any],
    publication_record_ref: str,
    transport_ref: str = LOCAL_JSONL,
    service: str = "zone-router",
) -> dict[str, Any]:
    if transport_ref not in SUPPORTED_TRANSPORTS:
        return _failure_evidence(
            record=record,
            publication_record_ref=publication_record_ref,
            transport_ref=transport_ref,
            error=f"unsupported transport_ref={transport_ref!r}",
            service=service,
        )
    if transport_ref == FAIL_TEST:
        return _failure_evidence(
            record=record,
            publication_record_ref=publication_record_ref,
            transport_ref=transport_ref,
            error="forced failure for transport://fail/test",
            service=service,
        )
    if transport_ref == KAFKA_REMOTE:
        missing = _missing_remote_kafka_config()
        if missing:
            return _failure_evidence(
                record=record,
                publication_record_ref=publication_record_ref,
                transport_ref=transport_ref,
                error="remote Kafka transport requires configuration: " + ", ".join(missing),
                service=service,
            )
        return _failure_evidence(
            record=record,
            publication_record_ref=publication_record_ref,
            transport_ref=transport_ref,
            error="remote Kafka broker client is not implemented in this safe seam",
            service=service,
        )

    return _write_local_delivery(record=record, publication_record_ref=publication_record_ref, transport_ref=transport_ref, service=service)
