from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_file_writeback_endpoint_returns_file_store_marker() -> None:
    response = client.post("/v0/wopi/file-writeback/demo-doc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == "demo-doc"
    assert payload["status"] == "WRITTEN"
    assert payload["store"] == "file"
    assert payload["version_id"] == "version-demo-doc-001"
