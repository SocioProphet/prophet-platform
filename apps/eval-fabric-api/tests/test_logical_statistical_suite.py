from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main

FIXTURES = Path(__file__).parent / "fixtures"


class _Emission:
    def __init__(self) -> None:
        self.payload_ref = "file:///tmp/payload.json"
        self.event_ref = "file:///tmp/event.json"
        self.receipt_ref = "file:///tmp/receipt.json"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture()
def logical_suite():
    return _load("logical_statistical_suite_0001.json")


@pytest.fixture()
def agent_spec():
    return _load("agent_spec_0001.json")


@pytest.fixture()
def ray_recipe():
    return _load("ray_recipe_lifecycle_0001.json")


@pytest.fixture()
def test_block():
    return _load("test_block_0001.json")


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main, "maybe_emit_artifacts", lambda **kwargs: _Emission())
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
                "source_trust_classes": ["internal_reproduced"],
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


def test_upstream_profile_alignment(logical_suite, agent_spec, ray_recipe, test_block) -> None:
    expected_profiles = {
        "EVIDENCE_PROFILE_0001",
        "CONTROL_GATING_GRADUATION_PROFILE_0001",
        "ORCHESTRATION_RAY_PROFILE_0001",
        "LOGICAL_STATISTICAL_PROFILE_0001",
        "TEST_BUILDING_BLOCK_PROFILE_0001",
    }
    assert expected_profiles.issubset(set(logical_suite["upstream_refs"]["profiles"]))
    assert "evidence_profile_0001" in agent_spec["profiles"]
    assert "control_gating_graduation_profile_0001" in agent_spec["profiles"]
    assert "orchestration_ray_profile_0001" in agent_spec["profiles"]
    assert test_block["expected_outputs"]["selected_route"] == "logical_route"
    assert test_block["expected_outputs"]["selected_action_profile"] == "tool_write"
    assert "ray_train_fit" in ray_recipe["lifecycle"]
    assert "ray_serve_promote" in ray_recipe["lifecycle"]


def test_route_inventory_matches_suite(logical_suite) -> None:
    app_routes = {route.path for route in main.app.routes}
    for route_path in logical_suite["route_expectations"]:
        assert route_path in app_routes


def test_frontier_and_provenance_routes_emit_evidence_headers(client: TestClient) -> None:
    frontier = client.get("/v1/frontier")
    assert frontier.status_code == 200
    assert frontier.json()["provenance_mode"] == "trust-aware profile ranking"
    assert frontier.headers["X-Payload-Ref"] == "file:///tmp/payload.json"
    assert frontier.headers["X-Event-Envelope-Ref"] == "file:///tmp/event.json"
    assert frontier.headers["X-Evidence-Receipt-Ref"] == "file:///tmp/receipt.json"

    provenance = client.get("/v1/frontier/provenance")
    assert provenance.status_code == 200
    assert provenance.json()["subjects"][0]["model_release_id"] == "model.semantic-stack.2026-04-05"


def test_dossier_and_attribution_align_with_test_block(client: TestClient, test_block) -> None:
    dossier = client.get("/v1/models/model.semantic-stack.2026-04-05/dossier")
    assert dossier.status_code == 200
    body = dossier.json()
    assert body["metrics"][0]["metric_definition_id"] == "md_denotation_accuracy"
    assert body["attribution"]["attributions"]["model_delta"] == 0.03
    assert body["repro_ledger_entries"][0]["repro_ledger_entry_id"] == "repro_001"

    assert set(test_block["expected_gates"]) == {
        "authorization_gate",
        "scope_gate",
        "policy_gate",
        "risk_gate",
        "evidence_gate",
        "approval_gate",
        "rollback_gate",
    }


def test_governance_and_competition_views(client: TestClient, logical_suite) -> None:
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

    assert "ray_train_fit" in logical_suite["ray_lifecycle_expectations"]
    assert "ray_serve_promote" in logical_suite["ray_lifecycle_expectations"]
