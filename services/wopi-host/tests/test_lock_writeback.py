from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_lock_endpoint_returns_lock_token() -> None:
    response = client.post("/v0/wopi/lock/demo-doc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == "demo-doc"
    assert payload["status"] == "LOCKED"
    assert payload["lock_token"] == "lock-demo-doc"


def test_writeback_endpoint_returns_version() -> None:
    response = client.post("/v0/wopi/writeback/demo-doc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == "demo-doc"
    assert payload["status"] == "WRITTEN"
    assert payload["version_id"] == "version-demo-doc-001"
