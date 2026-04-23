from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_put_file_then_get_file_roundtrip() -> None:
    put_response = client.post(
        "/v0/wopi/put-file/demo-doc",
        json={"payload": "hello office world"},
    )
    assert put_response.status_code == 200
    put_payload = put_response.json()
    assert put_payload["document_id"] == "demo-doc"
    assert put_payload["status"] == "WRITTEN"
    assert put_payload["store"] == "payload"

    get_response = client.get("/v0/wopi/get-file/demo-doc")
    assert get_response.status_code == 200
    assert get_response.content == b"hello office world"
