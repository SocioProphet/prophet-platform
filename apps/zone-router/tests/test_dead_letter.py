from __future__ import annotations

from pathlib import Path

from zone_router.retry_policy import compute_next_retry_not_before, resolve_retry_policy
from zone_router.transport import publish_publication_record


def _make_record(tmp_path: Path, *, topic: str = "zone.edge.carrier.ingested.v1") -> dict:
    return {
        "version": "0.1",
        "publication_id": "pub-dead-letter-001",
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
        "retry_policy": {
            "max_attempts": 2,
            "backoff_seconds": 5,
            "strategy": "fixed",
            "dead_letter_on_terminal": True,
        },
    }


def test_retry_policy_resolution_supports_override(tmp_path: Path) -> None:
    record = _make_record(tmp_path)
    policy = resolve_retry_policy(record)
    assert policy["max_attempts"] == 2
    assert policy["backoff_seconds"] == 5
    assert policy["strategy"] == "fixed"


def test_retry_policy_computes_next_retry_before_terminal(tmp_path: Path) -> None:
    record = _make_record(tmp_path)
    policy = resolve_retry_policy(record)
    assert compute_next_retry_not_before(1, policy) is not None
    assert compute_next_retry_not_before(2, policy) is None


def test_dead_letter_emitted_after_terminal_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    record = _make_record(tmp_path)

    first = publish_publication_record(record, transport_ref="transport://fail/test")
    assert first["ok"] is False
    assert first["outcome"]["attempt"] == 1
    assert first["outcome"]["retry_eligible"] is True
    assert first["outcome"]["terminal"] is False
    assert first["outcome"]["next_retry_not_before"]

    second = publish_publication_record(record, transport_ref="transport://fail/test")
    assert second["ok"] is False
    assert second["outcome"]["attempt"] == 2
    assert second["outcome"]["retry_eligible"] is False
    assert second["outcome"]["terminal"] is True
    assert second["outcome"]["previous_outcome_ref"] == first["outcome"]["outcome_id"]
    assert second["dead_letter"]["ok"] is True
    assert Path(second["dead_letter"]["dead_letter_path"]).exists()
