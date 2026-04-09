from __future__ import annotations

import json
from pathlib import Path

import app.receipts as receipts


def test_maybe_emit_disabled(monkeypatch):
    monkeypatch.delenv("EVAL_FABRIC_EMIT_RECEIPTS", raising=False)
    result = receipts.maybe_emit_artifacts(
        event_type="eval.fabric.frontier.read",
        action="FrontierQuery",
        status="succeeded",
        subject_ref="profile://profile.high_assurance_enterprise_agent",
        payload={"ok": True},
    )
    assert result is None


def test_emit_artifacts_writes_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_FABRIC_EMIT_RECEIPTS", "1")
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))

    emission = receipts.maybe_emit_artifacts(
        event_type="eval.fabric.frontier.read",
        action="FrontierQuery",
        status="succeeded",
        subject_ref="profile://profile.high_assurance_enterprise_agent",
        payload={"profile_id": "profile.high_assurance_enterprise_agent", "subjects": []},
        scope_ref="scope://platform/eval-fabric",
        classifiers=["route:frontier"],
        metrics={"subject_count": 0},
        correlation_id="test-correlation-id",
    )
    assert emission is not None
    assert emission.payload_path.exists()
    assert emission.event_path.exists()
    assert emission.receipt_path.exists()

    event = json.loads(Path(emission.event_path).read_text(encoding="utf-8"))
    receipt = json.loads(Path(emission.receipt_path).read_text(encoding="utf-8"))

    assert event["producer"] == "apps/eval-fabric-api"
    assert event["event_type"] == "eval.fabric.frontier.read"
    assert receipt["service_ref"] == "apps/eval-fabric-api"
    assert receipt["status"] == "succeeded"
    assert receipt["hash_algo"] == "sha256"
