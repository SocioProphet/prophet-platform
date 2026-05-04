from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_document_summary_reflects_payload_and_versions() -> None:
    document_id = 'summary-doc'

    client.post(f'/v0/wopi/put-file/{document_id}', json={'payload': 'v1'})
    client.post(f'/v0/wopi/put-file/{document_id}', json={'payload': 'v2'})

    response = client.get(f'/v0/wopi/document-summary/{document_id}')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == document_id
    assert payload['has_session'] is True
    assert payload['version_counter'] == 2
    assert payload['versions'] == [f'version-{document_id}-001', f'version-{document_id}-002']
    assert payload['payload_metadata']['size_bytes'] == len(b'v2')
    assert payload['document_record']['version_head'] == f'version-{document_id}-002'
    assert payload['session_record']['status'] == 'OPEN'
    assert len(payload['version_records']) == 2
    assert len(payload['writeback_records']) == 2
