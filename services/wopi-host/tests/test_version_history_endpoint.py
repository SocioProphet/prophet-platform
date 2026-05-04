from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_version_history_tracks_put_file_versions() -> None:
    document_id = 'version-history-doc'

    client.post(f'/v0/wopi/put-file/{document_id}', json={'payload': 'v1'})
    client.post(f'/v0/wopi/put-file/{document_id}', json={'payload': 'v2'})

    response = client.get(f'/v0/wopi/versions/{document_id}')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == document_id
    assert payload['versions'] == [f'version-{document_id}-001', f'version-{document_id}-002']

    records = client.get(f'/v0/wopi/version-records/{document_id}')
    assert records.status_code == 200
    version_records = records.json()['version_records']
    assert [item['version_id'] for item in version_records] == payload['versions']
    assert version_records[-1]['capture_source'] == 'WOPI_WRITEBACK'
