from fastapi.testclient import TestClient

from app.backends import ACADEMY_RECORDS
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    ACADEMY_RECORDS.clear()


def academy_record() -> dict[str, object]:
    return {
        "header": {
            "object_id": "lsr_00000001",
            "object_type": "LearningSearchRecord",
            "object_version": "0.1.0",
            "created_at": "2026-04-24T19:55:00Z",
            "created_by_contributor_id": "system.alexandrian",
            "created_by_role": "system",
            "status": "draft",
            "policy_tags": ["learning-loop", "search", "evidence-first"],
        },
        "source": "ALEXANDRIAN_ACADEMY",
        "entity_type": "LEARNING_ACTION_EXPLANATION",
        "title": "Why next learning action was recommended",
        "text": "Review cited evidence span before attempting the next assessment item.",
        "target_ref": "llr_00000001",
        "evidence_ref_ids": ["ariadne.span.example.0001"],
        "memory_ref_ids": ["memory-mesh://learning-context/example-0001"],
        "search_ref_ids": ["sherlock://learning-search/example-0001"],
        "governance_ref_ids": ["oracle://evaluation/example-0001", "moirai://changeset/example-0001", "policy-fabric://decision/example-0001"],
        "agentplane_run_ref_ids": ["agentplane://run/example-0001"],
        "final_score": 1.0,
    }


def test_academy_ingest_accepts_learning_search_record() -> None:
    response = client.post("/v1/search/ingest/academy", json=academy_record())
    assert response.status_code == 200
    assert response.json()["source"] == "ALEXANDRIAN_ACADEMY"
    assert response.json()["header"]["object_id"] == "lsr_00000001"


def test_academy_record_is_queryable_when_cloud_scope_enabled() -> None:
    client.post("/v1/search/ingest/academy", json=academy_record())
    response = client.post(
        "/v0/search/query",
        json={
            "query_id": "q-academy",
            "actor_id": "user-1",
            "text": "evidence",
            "mode": "HYBRID",
            "limit": 10,
            "scope": {"cloud_workspace": True, "local_desktop": False, "memory": False},
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    academy_results = [item for item in results if item["source"] == "ALEXANDRIAN_ACADEMY"]
    assert academy_results
    assert academy_results[0]["entity_type"] == "LEARNING_ACTION_EXPLANATION"
    assert academy_results[0]["path_or_uri"] == "alexandrian://learning-search/lsr_00000001"
