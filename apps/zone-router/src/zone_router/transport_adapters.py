from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_topic(topic: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in str(topic))


def _adapter_root(deliveries_root: Path, adapter: str) -> Path:
    return deliveries_root / adapter


def _ensure_adapter_dirs(deliveries_root: Path, adapter: str) -> tuple[Path, Path]:
    root = _adapter_root(deliveries_root, adapter)
    records = root / "records"
    topics = root / "topics"
    records.mkdir(parents=True, exist_ok=True)
    topics.mkdir(parents=True, exist_ok=True)
    return records, topics


def _write_delivery_record(delivery: dict[str, Any], records_root: Path) -> Path:
    path = records_root / f"{delivery['delivery_id']}.delivery.json"
    path.write_text(json.dumps(delivery, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _append_topic_log(topics_root: Path, topic: str, payload: dict[str, Any]) -> Path:
    topic_path = topics_root / f"{_safe_topic(topic)}.jsonl"
    with topic_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")
    return topic_path


def _base_delivery(record: dict[str, Any], *, transport_ref: str, adapter: str) -> dict[str, Any]:
    return {
        "version": "0.1",
        "delivery_id": str(uuid.uuid4()),
        "publication_id": record["publication_id"],
        "created_at": _utc_now(),
        "transport_ref": transport_ref,
        "adapter": adapter,
        "status": "delivered",
        "zone_ref": record["zone_ref"],
        "event_type": record["event_type"],
        "topic": record["topic"],
        "carrier_ref": record["carrier_ref"],
        "event_ref": record["event_ref"],
        "receipt_ref": record["receipt_ref"],
        "catalog_ref": record["catalog_ref"],
    }


def deliver_local_jsonl(record: dict[str, Any], *, transport_ref: str, deliveries_root: Path) -> dict[str, Any]:
    adapter = "local-jsonl"
    records_root, topics_root = _ensure_adapter_dirs(deliveries_root, adapter)
    delivery = _base_delivery(record, transport_ref=transport_ref, adapter=adapter)
    delivery_path = _write_delivery_record(delivery, records_root)
    topic_log_path = _append_topic_log(topics_root, record["topic"], delivery)
    delivery["delivery_ref"] = str(delivery_path)
    delivery["topic_log_ref"] = str(topic_log_path)
    delivery_path.write_text(json.dumps(delivery, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "status": "published",
        "adapter": adapter,
        "delivery": delivery,
        "delivery_path": str(delivery_path),
        "topic_log_path": str(topic_log_path),
    }


def deliver_kafka_jsonl(record: dict[str, Any], *, transport_ref: str, deliveries_root: Path) -> dict[str, Any]:
    adapter = "kafka-jsonl"
    records_root, topics_root = _ensure_adapter_dirs(deliveries_root, adapter)
    delivery = _base_delivery(record, transport_ref=transport_ref, adapter=adapter)
    delivery["partition"] = 0
    delivery["key"] = record["carrier_ref"]
    delivery_path = _write_delivery_record(delivery, records_root)
    topic_log_path = _append_topic_log(topics_root, record["topic"], delivery)
    delivery["delivery_ref"] = str(delivery_path)
    delivery["topic_log_ref"] = str(topic_log_path)
    delivery_path.write_text(json.dumps(delivery, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "status": "published",
        "adapter": adapter,
        "delivery": delivery,
        "delivery_path": str(delivery_path),
        "topic_log_path": str(topic_log_path),
    }


def deliver_fail_test(record: dict[str, Any], *, transport_ref: str, deliveries_root: Path) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "failed",
        "adapter": "fail-test",
        "error": f"simulated transport failure for {transport_ref}",
        "carrier_ref": record.get("carrier_ref"),
        "topic": record.get("topic"),
    }


def dispatch_transport(record: dict[str, Any], *, transport_ref: str, deliveries_root: Path) -> dict[str, Any]:
    if transport_ref == "transport://local/jsonl":
        return deliver_local_jsonl(record, transport_ref=transport_ref, deliveries_root=deliveries_root)
    if transport_ref == "transport://kafka/jsonl":
        return deliver_kafka_jsonl(record, transport_ref=transport_ref, deliveries_root=deliveries_root)
    if transport_ref == "transport://fail/test":
        return deliver_fail_test(record, transport_ref=transport_ref, deliveries_root=deliveries_root)
    return {
        "ok": False,
        "status": "failed",
        "adapter": "unknown",
        "error": f"unsupported transport_ref: {transport_ref}",
        "carrier_ref": record.get("carrier_ref"),
        "topic": record.get("topic"),
    }
