from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_check_file_info_reflects_payload_presence() -> None:
    before = client.get('/v0/wopi/check-file-info/demo-doc')
    assert before.status_code == 200
    assert before.json()['has_payload'] is False

    client.post('/v0/wopi/put-file/demo-doc', json={'payload': 'payload bytes'})

    after = client.get('/v0/wopi/check-file-info/demo-doc')
    assert after.status_code == 200
    payload = after.json()
    assert payload['has_payload'] is True
    assert payload['version_counter'] == 1
