from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_payload_metadata_reports_size_and_hash() -> None:
    document_id = 'metadata-doc'

    client.post(f'/v0/wopi/put-file/{document_id}', json={'payload': 'hello office world'})

    response = client.get(f'/v0/wopi/payload-metadata/{document_id}')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == document_id
    assert payload['size_bytes'] == len(b'hello office world')
    assert len(payload['sha256']) == 64
