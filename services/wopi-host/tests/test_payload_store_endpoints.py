from fastapi.testclient import TestClient

from services.wopi_host.app.main import app


client = TestClient(app)


def test_put_file_then_get_file_roundtrip() -> None:
    document_id = 'payload-roundtrip-doc'

    put_response = client.post(
        f'/v0/wopi/put-file/{document_id}',
        json={'payload': 'hello office world'},
    )
    assert put_response.status_code == 200
    put_payload = put_response.json()
    assert put_payload['document_id'] == document_id
    assert put_payload['status'] == 'WRITTEN'
    assert put_payload['store'] == 'payload'
    assert put_payload['version_record']['document_id'] == document_id
    assert put_payload['writeback_record']['operation'] == 'WOPI_PUT_FILE'

    get_response = client.get(f'/v0/wopi/get-file/{document_id}')
    assert get_response.status_code == 200
    assert get_response.content == b'hello office world'
