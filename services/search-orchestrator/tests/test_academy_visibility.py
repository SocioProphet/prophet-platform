from fastapi.testclient import TestClient

from app.backends import reset_academy_records
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    reset_academy_records()


def academy_record() -> dict[str, object]:
    return {
        "header": {
            "object_id": "lsr_visibility_0001",
            "object_type": "LearningSearchRecord",
            "policy_tags": ["learning-loop", "search"],
        },
        "source": "ALEXANDRIAN_ACADEMY",
        "entity_type": "LEARNING_ACTION_EXPLANATION",
        "title": "Why next learning action was recommended",
        "text": "Visibility gated evidence explanation.",
        "target_ref": "llr_visibility_0001",
        "visibility": {
            "allowed_actor_ids": ["allowed-user"],
            "allowed_workspace_ids": ["academy-workspace"],
            "allowed_jurisdiction_ids": ["pa-us"],
        },
        "final_score": 1.0,
    }


def query(actor_id: str, workspace_id: str | None, jurisdiction_id: str | None) -> list[dict[str, object]]:
    payload = {
        "query_id": "q-visibility",
        "actor_id": actor_id,
        "text": "evidence",
        "mode": "HYBRID",
        "limit": 10,
        "scope": {"cloud_workspace": True, "local_desktop": False, "memory": False},
    }
    if workspace_id is not None:
        payload["workspace_id"] = workspace_id
    if jurisdiction_id is not None:
        payload["jurisdiction_id"] = jurisdiction_id
    response = client.post("/v0/search/query", json=payload)
    assert response.status_code == 200
    return [item for item in response.json()["results"] if item["source"] == "ALEXANDRIAN_ACADEMY"]


def test_academy_visibility_allows_matching_actor_workspace_and_jurisdiction() -> None:
    assert client.post("/v1/search/ingest/academy", json=academy_record()).status_code == 200
    results = query("allowed-user", "academy-workspace", "pa-us")
    assert len(results) == 1


def test_academy_visibility_denies_wrong_actor() -> None:
    assert client.post("/v1/search/ingest/academy", json=academy_record()).status_code == 200
    assert query("other-user", "academy-workspace", "pa-us") == []


def test_academy_visibility_denies_missing_workspace() -> None:
    assert client.post("/v1/search/ingest/academy", json=academy_record()).status_code == 200
    assert query("allowed-user", None, "pa-us") == []
