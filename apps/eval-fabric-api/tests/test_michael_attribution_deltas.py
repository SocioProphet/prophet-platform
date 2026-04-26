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
    monkeypatch.setattr(
        main.governance_repositories,
        "get_model_attribution",
        lambda model_release_id, window="rolling_30d": {
            "subject_id": model_release_id,
            "window": window,
            "attributions": {
                "belief_delta": 0.11,
                "rule_delta": 0.07,
                "law_delta": 0.03,
                "constraint_delta": 0.02,
                "model_delta": 0.19,
            },
            "notes": "machine science attribution example",
        },
    )
    return TestClient(main.app)


def test_model_attribution_route_carries_michael_delta_fields(client: TestClient) -> None:
    response = client.get("/v1/models/model.semantic-stack.2026-04-05/attribution")
    assert response.status_code == 200
    body = response.json()
    attrs = body["attribution"]["attributions"]

    assert attrs["belief_delta"] == 0.11
    assert attrs["rule_delta"] == 0.07
    assert attrs["law_delta"] == 0.03
    assert attrs["constraint_delta"] == 0.02
    assert attrs["model_delta"] == 0.19
    assert body["window"] == "rolling_30d"
    assert response.headers["X-Payload-Ref"] == "file:///tmp/payload.json"
    assert response.headers["X-Event-Envelope-Ref"] == "file:///tmp/event.json"
    assert response.headers["X-Evidence-Receipt-Ref"] == "file:///tmp/receipt.json"
