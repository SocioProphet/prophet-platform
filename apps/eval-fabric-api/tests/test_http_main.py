from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)


def test_healthz_is_process_only():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "eval-fabric-api"
    assert payload["mode"] == "canonical"


def test_readyz_success(monkeypatch):
    monkeypatch.setattr(main, "pg_health", lambda: {"ok": True})
    monkeypatch.setattr(main, "ch_health", lambda: {"ok": True})

    resp = client.get("/readyz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["postgres"]["ok"] is True
    assert payload["clickhouse"]["ok"] is True


def test_readyz_degraded(monkeypatch):
    monkeypatch.setattr(main, "pg_health", lambda: {"ok": False, "error": "postgres down"})
    monkeypatch.setattr(main, "ch_health", lambda: {"ok": True})

    resp = client.get("/readyz")
    assert resp.status_code == 503
    payload = resp.json()
    assert payload["status"] == "degraded"
    assert payload["postgres"]["ok"] is False
    assert "error" in payload["postgres"]


def test_frontier_uses_repository(monkeypatch):
    expected = [{"subject_id": "model.semantic-stack.2026-04-05", "score": 0.782, "rank": 2}]
    monkeypatch.setattr(main.repositories, "get_frontier", lambda *args, **kwargs: expected)

    resp = client.get("/v1/frontier")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["profile_id"] == "profile.high_assurance_enterprise_agent"
    assert payload["subjects"] == expected
    assert payload["source"] == "clickhouse"
    assert payload["provenance_mode"] == "trust-aware profile ranking"


def test_frontier_emits_receipt_headers(monkeypatch, tmp_path):
    expected = [{"subject_id": "model.semantic-stack.2026-04-05", "score": 0.782, "rank": 2}]
    monkeypatch.setenv("EVAL_FABRIC_EMIT_RECEIPTS", "1")
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(main.repositories, "get_frontier", lambda *args, **kwargs: expected)

    resp = client.get("/v1/frontier")
    assert resp.status_code == 200
    payload_ref = resp.headers["X-Payload-Ref"]
    event_ref = resp.headers["X-Event-Envelope-Ref"]
    receipt_ref = resp.headers["X-Evidence-Receipt-Ref"]
    assert Path(payload_ref.removeprefix("file://")).exists()
    assert Path(event_ref.removeprefix("file://")).exists()
    assert Path(receipt_ref.removeprefix("file://")).exists()


def test_frontier_provenance_uses_repository_and_emits_headers(monkeypatch, tmp_path):
    expected = [{"model_release_id": "model.semantic-stack.2026-04-05", "metric_fact_count": 2}]
    monkeypatch.setenv("EVAL_FABRIC_EMIT_RECEIPTS", "1")
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(main.intelligence_repositories, "get_frontier_provenance", lambda limit=50: expected)

    resp = client.get("/v1/frontier/provenance?limit=7")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["subjects"] == expected
    assert payload["source"] == "clickhouse"
    assert resp.headers["X-Payload-Ref"]
    assert resp.headers["X-Event-Envelope-Ref"]
    assert resp.headers["X-Evidence-Receipt-Ref"]


def test_dossier_uses_repository(monkeypatch):
    expected_metrics = [{"metric_definition_id": "md_denotation_accuracy", "value_scalar": 0.84}]
    expected_attr = {"subject_id": "model.semantic-stack.2026-04-05"}
    expected_repro = [{"repro_ledger_entry_id": "rle_001"}]
    monkeypatch.setattr(main.repositories, "get_model_dossier", lambda model_release_id, limit=50: expected_metrics)
    monkeypatch.setattr(main.governance_repositories, "get_model_attribution", lambda model_release_id, window="rolling_30d": expected_attr)
    monkeypatch.setattr(main.governance_repositories, "get_model_repro_entries", lambda model_release_id: expected_repro)

    resp = client.get("/v1/models/model.semantic-stack.2026-04-05/dossier")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["model_release_id"] == "model.semantic-stack.2026-04-05"
    assert payload["metrics"] == expected_metrics
    assert payload["attribution"] == expected_attr
    assert payload["repro_ledger_entries"] == expected_repro
    assert payload["source"] == "clickhouse+postgres"


def test_model_attribution_route(monkeypatch):
    expected = {"subject_id": "model.semantic-stack.2026-04-05", "window": "rolling_30d"}
    monkeypatch.setattr(main.governance_repositories, "get_model_attribution", lambda model_release_id, window="rolling_30d": expected)

    resp = client.get("/v1/models/model.semantic-stack.2026-04-05/attribution?window=rolling_30d")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["attribution"] == expected
    assert payload["source"] == "postgres"


def test_run_provenance_route(monkeypatch):
    expected = {"run": {"run_id": "run_001"}}
    monkeypatch.setattr(main.governance_repositories, "get_run_provenance", lambda run_id: expected)

    resp = client.get("/v1/runs/run_001/provenance")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["provenance"] == expected
    assert payload["source"] == "postgres"


def test_governance_crosswalks_route(monkeypatch):
    expected = [{"metric_crosswalk_id": "mc_001"}]
    monkeypatch.setattr(main.governance_repositories, "get_metric_crosswalks", lambda limit=50: expected)

    resp = client.get("/v1/governance/crosswalks?limit=5")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["crosswalks"] == expected
    assert payload["source"] == "postgres"


def test_reproduced_vs_claimed_uses_repository(monkeypatch):
    expected = [{"provider_id": "openai", "coverage_state": "claimed_only"}]
    monkeypatch.setattr(main.intelligence_repositories, "get_reproduced_vs_claimed", lambda limit=50: expected)

    resp = client.get("/v1/competition/reproduced-vs-claimed?limit=9")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["items"] == expected
    assert payload["source"] == "postgres"


def test_radar_uses_repository(monkeypatch):
    expected = [{"provider_id": "openai", "model_release_id": "gpt5_aug2025"}]
    monkeypatch.setattr(main.repositories, "get_competition_radar", lambda limit=50: expected)

    resp = client.get("/v1/competition/radar")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["lane"] == "high_assurance_enterprise_agent"
    assert payload["competitors"] == expected
    assert payload["source"] == "postgres"
