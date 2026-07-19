from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_thread_resolution_records_version_and_receipt() -> None:
    client.post(
        '/v0/office-collaboration/threads',
        json={'thread_id': 't1', 'document_id': 'doc1', 'thread_type': 'COMMENT'},
    )
    resolved = client.post(
        '/v0/office-collaboration/threads/t1/status',
        json={'status': 'RESOLVED', 'version_id': 'version-doc1-002', 'receipt_ref': 'receipt-1'},
    )
    assert resolved.status_code == 200
    assert resolved.json()['status'] == 'RESOLVED'
    assert resolved.json()['version_id'] == 'version-doc1-002'
    assert resolved.json()['receipt_ref'] == 'receipt-1'


def test_suggestion_retrieval_and_listing() -> None:
    client.post(
        '/v0/office-collaboration/suggestions',
        json={'suggestion_id': 's1', 'document_id': 'doc1', 'before_ref': 'before', 'after_ref': 'after'},
    )
    fetched = client.get('/v0/office-collaboration/suggestions/s1')
    assert fetched.status_code == 200
    assert fetched.json()['suggestion_id'] == 's1'

    listed = client.get('/v0/office-collaboration/documents/doc1/suggestions')
    assert listed.status_code == 200
    assert listed.json()['suggestions'][0]['suggestion_id'] == 's1'
