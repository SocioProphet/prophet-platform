from __future__ import annotations

from pathlib import Path

from zone_router.transport_adapters import dispatch_transport


def _make_record(tmp_path: Path, *, topic: str = "zone.edge.carrier.ingested.v1") -> dict:
    return {
        "version": "0.1",
        "publication_id": "pub-001",
        "created_at": "2026-04-20T00:00:00Z",
        "service_ref": "apps/zone-router",
        "status": "planned",
        "zone_ref": "zone://edge",
        "event_type": "carrier.ingested",
        "topic": topic,
        "publication_mode": "resolved",
        "carrier_ref": "carrier://sha256/example",
        "event_ref": str(tmp_path / "event.json"),
        "receipt_ref": str(tmp_path / "receipt.json"),
        "catalog_ref": str(tmp_path / "catalog.jsonl"),
    }


def test_dispatch_transport_local_jsonl_writes_delivery_and_topic_log(tmp_path: Path) -> None:
    result = dispatch_transport(
        _make_record(tmp_path),
        transport_ref="transport://local/jsonl",
        deliveries_root=tmp_path / "deliveries",
    )
    assert result["ok"] is True
    assert result["adapter"] == "local-jsonl"
    assert Path(result["delivery_path"]).exists()
    assert Path(result["topic_log_path"]).exists()


def test_dispatch_transport_kafka_jsonl_writes_partitioned_delivery(tmp_path: Path) -> None:
    result = dispatch_transport(
        _make_record(tmp_path),
        transport_ref="transport://kafka/jsonl",
        deliveries_root=tmp_path / "deliveries",
    )
    assert result["ok"] is True
    assert result["adapter"] == "kafka-jsonl"
    assert result["delivery"]["partition"] == 0
    assert result["delivery"]["key"] == "carrier://sha256/example"


def test_dispatch_transport_fail_test_returns_failure(tmp_path: Path) -> None:
    result = dispatch_transport(
        _make_record(tmp_path),
        transport_ref="transport://fail/test",
        deliveries_root=tmp_path / "deliveries",
    )
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["adapter"] == "fail-test"
