from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_suggestion_event_history_tracks_create_and_status_change() -> None:
    created = client.post(
        '/v0/office-collaboration/suggestions',
        json={
            'suggestion_id': 's1',
            'document_id': 'doc1',
            'before_ref': 'before',
            'after_ref': 'after',
        },
    )
    assert created.status_code == 200

    updated = client.post(
        '/v0/office-collaboration/suggestions/s1/status',
        json={'status': 'ACCEPTED', 'version_id': 'version-doc1-002', 'receipt_ref': 'receipt-2'},
    )
    assert updated.status_code == 200

    events = client.get('/v0/office-collaboration/suggestions/s1/events')
    assert events.status_code == 200
    assert events.json()['events'][0]['event_type'] == 'SUGGESTION_CREATED'
    assert events.json()['events'][-1]['event_type'] == 'SUGGESTION_STATUS_UPDATED'
    assert events.json()['events'][-1]['version_id'] == 'version-doc1-002'
    assert events.json()['events'][-1]['receipt_ref'] == 'receipt-2'
