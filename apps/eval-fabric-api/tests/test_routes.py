from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main, "maybe_emit_artifacts", lambda **kwargs: None)
    monkeypatch.setattr(main, "pg_health", lambda: {"ok": True})
    monkeypatch.setattr(main, "ch_health", lambda: {"ok": True})

    monkeypatch.setattr(
        main.repositories,
        "get_frontier",
        lambda: [
            {"subject_id": "model.semantic-stack.2026-04-05", "score": 0.782, "rank": 2},
            {"subject_id": "gpt5_aug2025", "score": 0.801, "rank": 1},
        ],
    )
    monkeypatch.setattr(
        main.intelligence_repositories,
        "get_frontier_provenance",
        lambda limit=50: [
            {
                "model_release_id": "model.semantic-stack.2026-04-05",
                "metric_fact_count": 2,
                "reproduced_fact_count": 2,
            }
        ],
    )
    monkeypatch.setattr(
        main.repositories,
        "get_model_dossier",
        lambda model_release_id: [
            {"metric_definition_id": "md_denotation_accuracy", "value_scalar": 0.84}
        ],
    )
    monkeypatch.setattr(
        main.governance_repositories,
        "get_model_attribution",
        lambda model_release_id, window="rolling_30d": {
            "subject_id": model_release_id,
            "window": window,
            "attributions": {"model_delta": 0.03},
        },
    )
    monkeypatch.setattr(
        main.governance_repositories,
        "get_model_repro_entries",
        lambda model_release_id: [
            {"repro_ledger_entry_id": "repro_001", "run_id": "run_001"}
        ],
    )
    monkeypatch.setattr(
        main.governance_repositories,
        "get_run_provenance",
        lambda run_id: {
            "run": {"run_id": run_id},
            "repro_ledger_entries": [],
            "methodology_snapshots": [],
        },
    )
    monkeypatch.setattr(
        main.governance_repositories,
        "get_metric_crosswalks",
        lambda limit=50: [{"metric_crosswalk_id": "crosswalk_001"}],
    )
    monkeypatch.setattr(
        main.intelligence_repositories,
        "get_reproduced_vs_claimed",
        lambda limit=50: [{"competitor_snapshot_id": "cmp_openai", "coverage_state": "claimed_only"}],
    )
    monkeypatch.setattr(
        main.repositories,
        "get_competition_radar",
        lambda: [{"provider_id": "openai"}, {"provider_id": "google"}],
    )
    return TestClient(main.app)


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "eval-fabric-api"


def test_readyz_ok(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"]["ok"] is True
    assert body["clickhouse"]["ok"] is True


def test_frontier_routes(client: TestClient) -> None:
    frontier = client.get("/v1/frontier")
    assert frontier.status_code == 200
    body = frontier.json()
    assert body["profile_id"] == "profile.high_assurance_enterprise_agent"
    assert len(body["subjects"]) == 2
    assert body["provenance_mode"] == "trust-aware profile ranking"

    provenance = client.get("/v1/frontier/provenance")
    assert provenance.status_code == 200
    assert provenance.json()["subjects"][0]["model_release_id"] == "model.semantic-stack.2026-04-05"


def test_model_routes(client: TestClient) -> None:
    dossier = client.get("/v1/models/model.semantic-stack.2026-04-05/dossier")
    assert dossier.status_code == 200
    body = dossier.json()
    assert body["model_release_id"] == "model.semantic-stack.2026-04-05"
    assert body["metrics"][0]["metric_definition_id"] == "md_denotation_accuracy"
    assert body["attribution"]["attributions"]["model_delta"] == 0.03
    assert body["repro_ledger_entries"][0]["repro_ledger_entry_id"] == "repro_001"

    attribution = client.get("/v1/models/model.semantic-stack.2026-04-05/attribution")
    assert attribution.status_code == 200
    assert attribution.json()["attribution"]["window"] == "rolling_30d"


def test_governance_and_competition_routes(client: TestClient) -> None:
    run_provenance = client.get("/v1/runs/run_001/provenance")
    assert run_provenance.status_code == 200
    assert run_provenance.json()["provenance"]["run"]["run_id"] == "run_001"

    crosswalks = client.get("/v1/governance/crosswalks")
    assert crosswalks.status_code == 200
    assert crosswalks.json()["crosswalks"][0]["metric_crosswalk_id"] == "crosswalk_001"

    reproduced = client.get("/v1/competition/reproduced-vs-claimed")
    assert reproduced.status_code == 200
    assert reproduced.json()["items"][0]["coverage_state"] == "claimed_only"

    radar = client.get("/v1/competition/radar")
    assert radar.status_code == 200
    providers = {item["provider_id"] for item in radar.json()["competitors"]}
    assert {"openai", "google"}.issubset(providers)
