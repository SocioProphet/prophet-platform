from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_thread_messages_roundtrip() -> None:
    client.post(
        '/v0/office-collaboration/threads',
        json={'thread_id': 't1', 'document_id': 'doc1', 'thread_type': 'COMMENT'},
    )
    msg = client.post(
        '/v0/office-collaboration/threads/t1/messages',
        json={'message_id': 'm1', 'actor_ref': 'user-1', 'body': 'Needs a wording change.'},
    )
    assert msg.status_code == 200

    fetched = client.get('/v0/office-collaboration/threads/t1/messages')
    assert fetched.status_code == 200
    assert fetched.json()['messages'][0]['body'] == 'Needs a wording change.'


def test_suggestion_status_records_version() -> None:
    client.post(
        '/v0/office-collaboration/suggestions',
        json={'suggestion_id': 's1', 'document_id': 'doc1', 'before_ref': 'before', 'after_ref': 'after'},
    )
    update = client.post(
        '/v0/office-collaboration/suggestions/s1/status',
        json={'status': 'ACCEPTED', 'version_id': 'version-doc1-002'},
    )
    assert update.status_code == 200
    assert update.json()['status'] == 'ACCEPTED'
    assert update.json()['version_id'] == 'version-doc1-002'
