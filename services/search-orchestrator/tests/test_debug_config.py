from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_debug_config_reports_modes_without_paths_or_urls() -> None:
    response = client.get("/v1/search/debug/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "search-orchestrator"
    assert payload["academy_repository"]["mode"] in {
        "in-memory",
        "json-file",
        "lampstand-jsonl",
        "lampstand-carrier",
    }
    assert payload["academy_policy"]["mode"] in {"local-fallback", "http-policy-fabric"}
    text = str(payload)
    assert "http://" not in text
    assert "https://" not in text
    assert "/tmp/" not in text
    assert "SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT" not in text
