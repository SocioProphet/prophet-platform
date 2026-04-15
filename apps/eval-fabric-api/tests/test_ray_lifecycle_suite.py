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
def ray_recipe():
    return _load("ray_recipe_lifecycle_0001.json")


@pytest.fixture()
def logical_suite():
    return _load("logical_statistical_suite_0001.json")


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
        lambda: [{"subject_id": "model.semantic-stack.2026-04-05", "score": 0.782, "rank": 2}],
    )
    monkeypatch.setattr(
        main.intelligence_repositories,
        "get_reproduced_vs_claimed",
        lambda limit=50: [{"competitor_snapshot_id": "cmp_openai", "coverage_state": "claimed_only"}],
    )
    return TestClient(main.app)


def test_ray_lifecycle_fixture_matches_suite(ray_recipe, logical_suite) -> None:
    assert ray_recipe["controller"] == "ray_orchestrator"
    assert ray_recipe["lifecycle"] == [
        "ray_data_prepare",
        "ray_train_fit",
        "ray_tune_search",
        "benchmark_evaluate",
        "ray_serve_promote",
    ]
    assert logical_suite["ray_lifecycle_expectations"] == ray_recipe["lifecycle"]
    assert "promotion_decision" in ray_recipe["outputs"]
    assert "benchmark_report" in ray_recipe["outputs"]


def test_ray_promotion_requires_expected_gates(test_block) -> None:
    expected = {
        "authorization_gate",
        "scope_gate",
        "policy_gate",
        "risk_gate",
        "evidence_gate",
        "approval_gate",
        "rollback_gate",
    }
    assert set(test_block["expected_gates"]) == expected
    assert test_block["expected_outputs"]["selected_action_profile"] == "tool_write"


def test_business_routes_emit_evidence_for_lifecycle_surfaces(client: TestClient, ray_recipe) -> None:
    frontier = client.get("/v1/frontier")
    assert frontier.status_code == 200
    assert frontier.headers["X-Payload-Ref"] == "file:///tmp/payload.json"
    assert frontier.headers["X-Event-Envelope-Ref"] == "file:///tmp/event.json"
    assert frontier.headers["X-Evidence-Receipt-Ref"] == "file:///tmp/receipt.json"

    reproduced = client.get("/v1/competition/reproduced-vs-claimed")
    assert reproduced.status_code == 200
    assert reproduced.headers["X-Payload-Ref"] == "file:///tmp/payload.json"
    assert reproduced.headers["X-Event-Envelope-Ref"] == "file:///tmp/event.json"
    assert reproduced.headers["X-Evidence-Receipt-Ref"] == "file:///tmp/receipt.json"

    assert "event_envelope" in ray_recipe["outputs"]
    assert "evidence_receipt" in ray_recipe["outputs"]


def test_readyz_remains_green_for_promotion_path(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"]["ok"] is True
    assert body["clickhouse"]["ok"] is True
