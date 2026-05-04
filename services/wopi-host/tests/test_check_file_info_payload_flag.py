from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_check_file_info_reflects_payload_presence() -> None:
    document_id = 'check-info-doc'

    before = client.get(f'/v0/wopi/check-file-info/{document_id}')
    assert before.status_code == 200
    assert before.json()['has_payload'] is False

    client.post(f'/v0/wopi/put-file/{document_id}', json={'payload': 'payload bytes'})

    after = client.get(f'/v0/wopi/check-file-info/{document_id}')
    assert after.status_code == 200
    payload = after.json()
    assert payload['has_payload'] is True
    assert payload['version_counter'] == 1
    assert payload['document_record']['document_id'] == document_id
    assert payload['document_record']['source_provider'] == 'SOURCEOS'
