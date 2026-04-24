from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_document_summary_reflects_payload_and_versions() -> None:
    client.post('/v0/wopi/put-file/demo-doc', json={'payload': 'v1'})
    client.post('/v0/wopi/put-file/demo-doc', json={'payload': 'v2'})

    response = client.get('/v0/wopi/document-summary/demo-doc')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == 'demo-doc'
    assert payload['has_session'] is True
    assert payload['version_counter'] == 2
    assert payload['versions'] == ['version-demo-doc-001', 'version-demo-doc-002']
    assert payload['payload_metadata']['size_bytes'] == len(b'v2')
