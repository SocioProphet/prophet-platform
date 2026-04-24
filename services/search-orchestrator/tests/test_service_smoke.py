from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.json()['service'] == 'search-orchestrator'


def test_query_endpoint_returns_normalized_empty_results() -> None:
    response = client.post(
        '/v0/search/query',
        json={
            'query_id': 'q1',
            'actor_id': 'user-1',
            'text': 'budget',
            'mode': 'HYBRID',
            'limit': 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['query_id'] == 'q1'
    assert payload['actor_id'] == 'user-1'
    assert payload['mode'] == 'HYBRID'
    assert payload['results'] == []
