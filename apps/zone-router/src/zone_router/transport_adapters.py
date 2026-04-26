from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .outbox import publication_outbox_root

LOCAL_JSONL = "transport://local/jsonl"
KAFKA_JSONL = "transport://kafka/jsonl"
SUPPORTED_TRANSPORTS = {LOCAL_JSONL, KAFKA_JSONL}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _transport_kind(transport_ref: str) -> str:
    if transport_ref == LOCAL_JSONL:
        return "local-jsonl"
    if transport_ref == KAFKA_JSONL:
        return "kafka-jsonl-local-standin"
    raise ValueError(f"unsupported transport_ref={transport_ref!r}")


def _deliveries_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "deliveries"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _topic_logs_root(service: str = "zone-router") -> Path:
    root = publication_outbox_root(service) / "topic-logs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_topic(topic: str) -> str:
    return topic.replace("/", "_").replace(":", "_")


def deliver_publication_record(
    *,
    record: dict[str, Any],
    publication_record_ref: str,
    transport_ref: str = LOCAL_JSONL,
    service: str = "zone-router",
) -> dict[str, Any]:
    if transport_ref not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"unsupported transport_ref={transport_ref!r}")

    delivery_id = str(uuid.uuid4())
    delivery = {
        "version": "0.1",
        "delivery_id": delivery_id,
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

    delivery_path = _deliveries_root(service) / f"{delivery_id}.delivery.json"
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
