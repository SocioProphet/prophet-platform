from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_thread_add_message_and_resolve() -> None:
    create = client.post(
        '/v0/office-collaboration/threads',
        json={
            'thread_id': 't1',
            'document_id': 'doc1',
            'thread_type': 'COMMENT',
        },
    )
    assert create.status_code == 200

    msg = client.post(
        '/v0/office-collaboration/threads/t1/messages',
        json={
            'message_id': 'm1',
            'actor_ref': 'user-1',
            'body': 'Needs a wording change.',
        },
    )
    assert msg.status_code == 200

    fetched = client.get('/v0/office-collaboration/threads/t1/messages')
    assert fetched.status_code == 200
    assert fetched.json()['messages'][0]['body'] == 'Needs a wording change.'

    resolved = client.post(
        '/v0/office-collaboration/threads/t1/status',
        json={'status': 'RESOLVED', 'version_id': 'version-doc1-002', 'receipt_ref': 'receipt-1'},
    )
    assert resolved.status_code == 200
    assert resolved.json()['status'] == 'RESOLVED'
    assert resolved.json()['version_id'] == 'version-doc1-002'
    assert resolved.json()['receipt_ref'] == 'receipt-1'


def test_create_and_update_suggestion() -> None:
    create = client.post(
        '/v0/office-collaboration/suggestions',
        json={
            'suggestion_id': 's1',
            'document_id': 'doc1',
            'before_ref': 'before',
            'after_ref': 'after',
        },
    )
    assert create.status_code == 200
    assert create.json()['status'] == 'PROPOSED'

    fetched = client.get('/v0/office-collaboration/suggestions/s1')
    assert fetched.status_code == 200
    assert fetched.json()['suggestion_id'] == 's1'

    listed = client.get('/v0/office-collaboration/documents/doc1/suggestions')
    assert listed.status_code == 200
    assert listed.json()['suggestions'][0]['suggestion_id'] == 's1'

    update = client.post(
        '/v0/office-collaboration/suggestions/s1/status',
        json={'status': 'ACCEPTED', 'version_id': 'version-doc1-002', 'receipt_ref': 'receipt-2'},
    )
    assert update.status_code == 200
    assert update.json()['status'] == 'ACCEPTED'
    assert update.json()['version_id'] == 'version-doc1-002'
    assert update.json()['receipt_ref'] == 'receipt-2'
