from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_cloud_workspace_scope_returns_platform_result() -> None:
    response = client.post(
        '/v0/search/query',
        json={
            'query_id': 'q1',
            'actor_id': 'user-1',
            'text': 'budget',
            'mode': 'HYBRID',
            'limit': 5,
            'scope': {'cloud_workspace': True, 'local_desktop': False, 'memory': False},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['results'][0]['source'] == 'PLATFORM'
    assert payload['results'][0]['entity_type'] == 'DOCUMENT'
    assert payload['results'][0]['snippet'] == 'Matched workspace content for query: budget'
    assert payload['results'][0]['path_or_uri'] == 'workspace://documents/budget'
