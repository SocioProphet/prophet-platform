from fastapi.testclient import TestClient

from app.metrics import reset
from app.main import app

client = TestClient(app)


def academy_record() -> dict[str, object]:
    return {
        "header": {
            "object_id": "lsr_metrics_0001",
            "object_type": "LearningSearchRecord",
            "policy_tags": ["learning-loop", "search"],
        },
        "source": "ALEXANDRIAN_ACADEMY",
        "entity_type": "LEARNING_ACTION_EXPLANATION",
        "title": "Why recommended",
        "text": "Metrics smoke evidence explanation.",
        "target_ref": "llr_metrics_0001",
        "final_score": 1.0,
    }


def test_debug_metrics_reports_counters_without_sensitive_values() -> None:
    reset()
    assert client.post("/v1/search/ingest/academy", json=academy_record()).status_code == 200
    query_response = client.post(
        "/v0/search/query",
        json={
            "query_id": "q-metrics",
            "actor_id": "user-1",
            "text": "evidence",
            "mode": "HYBRID",
            "limit": 10,
            "scope": {"cloud_workspace": True, "local_desktop": False, "memory": False},
        },
    )
    assert query_response.status_code == 200

    response = client.get("/v1/search/debug/metrics")
    assert response.status_code == 200
    payload = response.json()
    metrics = payload["metrics"]
    assert metrics["academy_ingest_total"] == 1
    assert metrics["search_query_total"] == 1
    assert metrics["academy_result_total"] >= 1
    text = str(payload)
    assert "user-1" not in text
    assert "q-metrics" not in text
    assert "http://" not in text
    assert "https://" not in text
    assert "/tmp/" not in text
