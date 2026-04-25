import importlib

from fastapi.testclient import TestClient


def academy_record() -> dict[str, object]:
    return {
        "header": {
            "object_id": "lsr_deploy_smoke_0001",
            "object_type": "LearningSearchRecord",
            "policy_tags": ["learning-loop", "search"],
        },
        "source": "ALEXANDRIAN_ACADEMY",
        "entity_type": "LEARNING_ACTION_EXPLANATION",
        "title": "Why recommended",
        "text": "Deployment smoke evidence explanation.",
        "target_ref": "llr_deploy_smoke_0001",
        "evidence_ref_ids": ["evidence://academy/span/0001"],
        "final_score": 1.0,
    }


def load_configured_app(monkeypatch, tmp_path):
    monkeypatch.setenv("SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_CARRIER_DIR", str(tmp_path / "academy-carriers"))
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("SOCIOPROFIT_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("SOCIOPROFIT_RUNTIME_HOME", str(tmp_path / "runtime"))

    import app.repositories as repositories
    import app.policy as policy
    import app.backends as backends
    import app.main as main

    importlib.reload(repositories)
    importlib.reload(policy)
    importlib.reload(backends)
    importlib.reload(main)
    return main.app


def test_lampstand_carrier_deployment_smoke(monkeypatch, tmp_path) -> None:
    app = load_configured_app(monkeypatch, tmp_path)
    client = TestClient(app)

    config_response = client.get("/v1/search/debug/config")
    assert config_response.status_code == 200
    config = config_response.json()
    assert config["academy_repository"]["mode"] == "lampstand-carrier"
    assert config["academy_policy"]["mode"] == "local-fallback"

    ingest_response = client.post("/v1/search/ingest/academy", json=academy_record())
    assert ingest_response.status_code == 200

    query_response = client.post(
        "/v0/search/query",
        json={
            "query_id": "q-deploy-smoke",
            "actor_id": "user-1",
            "text": "evidence",
            "mode": "HYBRID",
            "limit": 10,
            "scope": {"cloud_workspace": True, "local_desktop": False, "memory": False},
        },
    )
    assert query_response.status_code == 200
    academy_results = [item for item in query_response.json()["results"] if item["source"] == "ALEXANDRIAN_ACADEMY"]
    assert academy_results

    state_root = tmp_path / "state" / "prophet-platform"
    assert list((tmp_path / "academy-carriers").glob("*.LearningSearchRecord.json"))
    assert list((state_root / "payloads" / "lampstand").glob("*.CarrierIngested.json"))
    assert list((state_root / "receipts" / "lampstand").glob("*.json"))
    assert list((state_root / "catalog" / "lampstand").glob("*.jsonl"))
