from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_lock_endpoint_returns_lock_token() -> None:
    document_id = 'lock-doc'

    response = client.post(f'/v0/wopi/lock/{document_id}')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == document_id
    assert payload['status'] == 'LOCKED'
    assert payload['lock_token'] == f'lock-{document_id}'
    assert payload['session_record']['document_id'] == document_id
    assert payload['session_record']['status'] == 'OPEN'


def test_refresh_and_unlock_endpoints_update_session_contract() -> None:
    document_id = 'lock-refresh-doc'

    lock_response = client.post(f'/v0/wopi/lock/{document_id}')
    assert lock_response.status_code == 200

    refresh_response = client.post(f'/v0/wopi/refresh-lock/{document_id}')
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload['status'] == 'LOCK_REFRESHED'
    assert refresh_payload['session_record']['status'] == 'OPEN'

    unlock_response = client.post(f'/v0/wopi/unlock/{document_id}')
    assert unlock_response.status_code == 200
    unlock_payload = unlock_response.json()
    assert unlock_payload['status'] == 'UNLOCKED'
    assert unlock_payload['session_record']['status'] == 'CLOSED'

    missing_refresh = client.post(f'/v0/wopi/refresh-lock/{document_id}')
    assert missing_refresh.status_code == 404


def test_writeback_endpoint_returns_version_and_contract_records() -> None:
    document_id = 'writeback-doc'

    response = client.post(f'/v0/wopi/writeback/{document_id}')
    assert response.status_code == 200
    payload = response.json()
    assert payload['document_id'] == document_id
    assert payload['status'] == 'WRITTEN'
    assert payload['version_id'] == f'version-{document_id}-001'
    assert payload['version_record']['version_id'] == payload['version_id']
    assert payload['version_record']['capture_source'] == 'WOPI_WRITEBACK'
    assert payload['writeback_record']['result_version_id'] == payload['version_id']
    assert payload['writeback_record']['status'] == 'COMMITTED'
