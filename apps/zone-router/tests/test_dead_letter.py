"""
Tests for retry policy, dead-letter artifact writing, and the integrated
publish_publication_record dead-letter path.

These tests verify:
  - retry policy resolution from record vs default
  - is_terminal_attempt logic
  - compute_next_retry_not_before (non-terminal → ISO string; terminal → None)
  - write_dead_letter creates artifact and log
  - publish_publication_record: first failure → retry_eligible, not terminal
  - publish_publication_record: second failure (max_attempts=2) → terminal, dead-letter written
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from zone_router.dead_letter import write_dead_letter
from zone_router.publish import publish_publication_record
from zone_router.retry_policy import (
    DEFAULT_RETRY_POLICY,
    compute_next_retry_not_before,
    is_terminal_attempt,
    resolve_retry_policy,
)


# ── retry policy unit tests ──────────────────────────────────────────────────

def test_resolve_retry_policy_defaults() -> None:
    record: dict = {}
    policy = resolve_retry_policy(record)
    assert policy["max_attempts"] == DEFAULT_RETRY_POLICY["max_attempts"]
    assert policy["retry_strategy"] == DEFAULT_RETRY_POLICY["retry_strategy"]
    assert policy["dead_letter_on_terminal"] is True


def test_resolve_retry_policy_override() -> None:
    record = {"retry_policy": {"max_attempts": 1, "dead_letter_on_terminal": False}}
    policy = resolve_retry_policy(record)
    assert policy["max_attempts"] == 1
    assert policy["dead_letter_on_terminal"] is False
    # non-overridden keys remain at default
    assert policy["retry_strategy"] == DEFAULT_RETRY_POLICY["retry_strategy"]


def test_is_terminal_attempt_not_yet() -> None:
    policy = {"max_attempts": 3}
    assert is_terminal_attempt(1, policy) is False
    assert is_terminal_attempt(2, policy) is False


def test_is_terminal_attempt_at_max() -> None:
    policy = {"max_attempts": 3}
    assert is_terminal_attempt(3, policy) is True
    assert is_terminal_attempt(4, policy) is True


def test_compute_next_retry_not_before_non_terminal() -> None:
    policy = {"max_attempts": 3, "retry_backoff_seconds": 30, "retry_strategy": "fixed"}
    result = compute_next_retry_not_before(1, policy)
    assert result is not None
    # should be an ISO 8601 string
    assert "T" in result


def test_compute_next_retry_not_before_terminal() -> None:
    policy = {"max_attempts": 2, "retry_backoff_seconds": 30, "retry_strategy": "fixed"}
    result = compute_next_retry_not_before(2, policy)
    assert result is None


def test_compute_next_retry_not_before_exponential() -> None:
    policy = {"max_attempts": 5, "retry_backoff_seconds": 10, "retry_strategy": "exponential"}
    result = compute_next_retry_not_before(3, policy)
    assert result is not None


# ── dead_letter unit tests ────────────────────────────────────────────────────

def test_write_dead_letter_creates_artifact(tmp_path: Path) -> None:
    os.environ["SOCIOPROFIT_STATE_HOME"] = str(tmp_path / "state")
    try:
        result = write_dead_letter(
            publication_id="pub-test-001",
            outcome_id="outcome-test-001",
            outcome_ref="/tmp/outcome.json",
            failure_id="failure-test-001",
            failure_ref="/tmp/failure.json",
            attempt=3,
            max_attempts=3,
            zone_ref="zone://edge",
            topic="zone.edge.carrier.ingested.v1",
            transport_ref="transport://fail/test",
            error="forced failure",
            service="zone-router",
        )
        assert result["dead_letter_id"]
        artifact_path = Path(result["dead_letter_ref"])
        assert artifact_path.exists()
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert artifact["publication_id"] == "pub-test-001"
        assert artifact["attempt"] == 3
        assert artifact["max_attempts"] == 3
        assert "non_claims" in artifact
        log_path = Path(result["log_path"])
        assert log_path.exists()
    finally:
        del os.environ["SOCIOPROFIT_STATE_HOME"]


# ── integration: publish_publication_record with dead-letter path ────────────

def _make_record(tmp_path: Path, publication_id: str, max_attempts: int = 2) -> Path:
    from zone_router.outbox import publication_records_root
    publication_records_root("zone-router").mkdir(parents=True, exist_ok=True)
    record_path = publication_records_root("zone-router") / f"{publication_id}.publication.json"
    record_path.write_text(
        json.dumps({
            "version": "0.1",
            "publication_id": publication_id,
            "created_at": "2026-06-09T12:00:00+00:00",
            "service_ref": "apps/zone-router",
            "status": "planned",
            "zone_ref": "zone://edge",
            "event_type": "carrier.ingested",
            "topic": "zone.edge.carrier.ingested.v1",
            "publication_mode": "local",
            "carrier_ref": "carrier://sha256/test",
            "event_ref": "event://test",
            "receipt_ref": None,
            "catalog_ref": None,
            "retry_policy": {
                "max_attempts": max_attempts,
                "retry_backoff_seconds": 1,
                "retry_strategy": "fixed",
                "dead_letter_on_terminal": True,
            },
        }),
        encoding="utf-8",
    )
    return record_path


def test_first_failure_is_retry_eligible(tmp_path: Path) -> None:
    os.environ["SOCIOPROFIT_STATE_HOME"] = str(tmp_path / "state")
    os.environ["SOCIOPROFIT_DATA_HOME"] = str(tmp_path / "data")
    os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(tmp_path / "run")
    try:
        pub_id = "pub-dead-letter-test-001"
        record_path = _make_record(tmp_path, pub_id, max_attempts=2)
        result = publish_publication_record(
            record_path=record_path,
            transport_ref="transport://fail/test",
        )
        outcome = result["outcome"]
        assert result["ok"] is False
        assert outcome["attempt"] == 1
        assert outcome["status"] == "failed"
        assert outcome["retry_eligible"] is True
        assert outcome["terminal"] is False
        assert outcome["next_retry_not_before"] is not None
        assert "dead_letter" not in result
    finally:
        for key in ["SOCIOPROFIT_STATE_HOME", "SOCIOPROFIT_DATA_HOME", "SOCIOPROFIT_RUNTIME_HOME"]:
            os.environ.pop(key, None)


def test_second_failure_is_terminal_with_dead_letter(tmp_path: Path) -> None:
    os.environ["SOCIOPROFIT_STATE_HOME"] = str(tmp_path / "state")
    os.environ["SOCIOPROFIT_DATA_HOME"] = str(tmp_path / "data")
    os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(tmp_path / "run")
    try:
        pub_id = "pub-dead-letter-test-002"
        record_path = _make_record(tmp_path, pub_id, max_attempts=2)

        first = publish_publication_record(
            record_path=record_path,
            transport_ref="transport://fail/test",
        )
        assert first["ok"] is False
        first_outcome = first["outcome"]
        assert first_outcome["attempt"] == 1
        assert first_outcome["terminal"] is False
        assert "dead_letter" not in first

        second = publish_publication_record(
            record_path=record_path,
            transport_ref="transport://fail/test",
        )
        assert second["ok"] is False
        second_outcome = second["outcome"]
        assert second_outcome["attempt"] == 2
        assert second_outcome["retry_eligible"] is False
        assert second_outcome["terminal"] is True
        assert second_outcome["next_retry_not_before"] is None
        assert second_outcome["previous_outcome_id"] == first_outcome["outcome_id"]

        assert "dead_letter" in second
        dead_letter_ref = second["dead_letter"]["dead_letter_ref"]
        assert Path(dead_letter_ref).exists()
        dl = json.loads(Path(dead_letter_ref).read_text(encoding="utf-8"))
        assert dl["publication_id"] == pub_id
        assert dl["attempt"] == 2
        assert dl["max_attempts"] == 2

        # failure evidence still present
        assert second_outcome.get("failure_ref")
    finally:
        for key in ["SOCIOPROFIT_STATE_HOME", "SOCIOPROFIT_DATA_HOME", "SOCIOPROFIT_RUNTIME_HOME"]:
            os.environ.pop(key, None)
