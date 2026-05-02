from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_and_fetch_thread() -> None:
    create = client.post(
        '/v0/office-collaboration/threads',
        json={
            'thread_id': 't1',
            'document_id': 'doc1',
            'thread_type': 'COMMENT',
        },
    )
    assert create.status_code == 200

    fetched = client.get('/v0/office-collaboration/threads/t1')
    assert fetched.status_code == 200
    assert fetched.json()['thread_id'] == 't1'
    assert fetched.json()['status'] == 'OPEN'


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

    update = client.post(
        '/v0/office-collaboration/suggestions/s1/status',
        json={'status': 'ACCEPTED'},
    )
    assert update.status_code == 200
    assert update.json()['status'] == 'ACCEPTED'
