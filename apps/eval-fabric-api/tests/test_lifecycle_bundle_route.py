from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main


class _Emission:
    def __init__(self) -> None:
        self.payload_ref = "file:///tmp/payload.json"
        self.event_ref = "file:///tmp/event.json"
        self.receipt_ref = "file:///tmp/receipt.json"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main, "maybe_emit_artifacts", lambda **kwargs: _Emission())
    return TestClient(main.app)


def test_lifecycle_bundle_route_returns_expected_shape(client: TestClient) -> None:
    response = client.get("/v1/models/model.semantic-stack.2026-04-05/lifecycle-bundle")
    assert response.status_code == 200
    body = response.json()

    assert body["model_release_id"] == "model.semantic-stack.2026-04-05"
    assert body["agent_ref"].startswith("agent://")
    assert body["recipe_ref"] == "recipe://benchmark/ray/eval-fabric-001"
    assert body["promotion_decision"]["subject_ref"] == "model://model.semantic-stack.2026-04-05"
    assert body["promotion_decision"]["target_stage"] == "L4_supervised_actuation"
    assert body["rollback_record"]["trigger_ref"] == body["promotion_decision"]["promotion_decision_id"]
    assert body["gate_activation_record"]["action_ref"].endswith("tool_write/logical_route")
    assert body["graduation_record"]["current_stage"] == "L3_assist_mode"
    assert len(body["artifact_graph"]["edges"]) == 4
    assert body["source"] == "runtime+builders"


def test_lifecycle_bundle_route_emits_receipt_headers(client: TestClient) -> None:
    response = client.get("/v1/models/model.semantic-stack.2026-04-05/lifecycle-bundle")
    assert response.status_code == 200
    assert response.headers["X-Payload-Ref"] == "file:///tmp/payload.json"
    assert response.headers["X-Event-Envelope-Ref"] == "file:///tmp/event.json"
    assert response.headers["X-Evidence-Receipt-Ref"] == "file:///tmp/receipt.json"
