from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_file_writeback_endpoint_returns_file_store_marker() -> None:
    document_id = 'file-writeback-doc'

    response = client.post(f'/v0/wopi/file-writeback/{document_id}')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == document_id
    assert payload['status'] == 'WRITTEN'
    assert payload['store'] == 'file'
    assert payload['version_id'] == f'version-{document_id}-001'
    assert payload['version_record']['execution_backend'] == 'COLLABORA'
    assert payload['writeback_record']['operation'] == 'WOPI_PUT_FILE'
