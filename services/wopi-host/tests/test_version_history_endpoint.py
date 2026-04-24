from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_version_history_tracks_put_file_versions() -> None:
    client.post('/v0/wopi/put-file/demo-doc', json={'payload': 'v1'})
    client.post('/v0/wopi/put-file/demo-doc', json={'payload': 'v2'})

    response = client.get('/v0/wopi/versions/demo-doc')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == 'demo-doc'
    assert payload['versions'] == ['version-demo-doc-001', 'version-demo-doc-002']
