from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_payload_metadata_reports_size_and_hash() -> None:
    client.post('/v0/wopi/put-file/demo-doc', json={'payload': 'hello office world'})

    response = client.get('/v0/wopi/payload-metadata/demo-doc')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == 'demo-doc'
    assert payload['size_bytes'] == len(b'hello office world')
    assert len(payload['sha256']) == 64
