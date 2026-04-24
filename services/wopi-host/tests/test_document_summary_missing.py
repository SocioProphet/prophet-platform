from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_document_summary_for_missing_doc_is_empty() -> None:
    response = client.get('/v0/wopi/document-summary/missing-doc')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == 'missing-doc'
    assert payload['has_session'] is False
    assert payload['version_counter'] == 0
    assert payload['versions'] == []
    assert payload['payload_metadata'] is None
