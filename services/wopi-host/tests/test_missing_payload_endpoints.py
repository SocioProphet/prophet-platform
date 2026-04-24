from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_missing_payload_endpoints_return_not_found() -> None:
    get_response = client.get('/v0/wopi/get-file/missing-doc')
    assert get_response.status_code == 404

    metadata_response = client.get('/v0/wopi/payload-metadata/missing-doc')
    assert metadata_response.status_code == 404
