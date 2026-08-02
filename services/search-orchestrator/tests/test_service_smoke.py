from fastapi.testclient import TestClient

from app.backends import reset_academy_records
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    reset_academy_records()


def test_health_endpoint() -> None:
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.json()['service'] == 'search-orchestrator'


def test_query_endpoint_returns_normalized_response_shape() -> None:
    # Renamed from test_query_endpoint_returns_normalized_empty_results: that name and
    # its results==[] assertion codified a real defect (KMASS baseline, 2026-08-01) --
    # SearchRequest.scope defaulted to None, and main.py read
    # `scope is not None and scope.cloud_workspace`, so a request with no scope field
    # at all silently returned nothing from every source, with no error. This exact
    # request shape (no scope) is what every KMASS baseline probe sent. Now that
    # SearchRequest.scope defaults to an enabled SearchScope(), the platform-workspace
    # source's placeholder stub (app/backends.py::query_platform_workspace -- it
    # deliberately echoes the query text back as a fake match, see its own docstring)
    # correctly fires, and this asserts that real behavior instead of the old bug.
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
    assert len(payload['results']) == 1
    assert payload['results'][0]['source'] == 'PLATFORM'
    assert payload['results'][0]['path_or_uri'] == 'workspace://documents/budget'


def test_query_endpoint_omitting_scope_is_not_silently_disabled() -> None:
    # The specific regression this defect needs: a query that matches a REAL,
    # non-placeholder, ingested record must return it even when the caller sends no
    # scope field -- not just the platform-workspace stub above. Exercises the same
    # academy path the KMASS baseline's 30 probe queries went through and found
    # permanently empty.
    record = {
        'header': {
            'object_id': 'lsr_default_scope_regression',
            'object_type': 'LearningSearchRecord',
            'policy_tags': ['learning-loop', 'search'],
        },
        'source': 'ALEXANDRIAN_ACADEMY',
        'entity_type': 'LEARNING_ACTION_EXPLANATION',
        'title': 'Default-scope regression fixture',
        'text': 'evidence about defaulting the search scope correctly',
        'target_ref': 'llr_default_scope_regression',
        'final_score': 1.0,
    }
    assert client.post('/v1/search/ingest/academy', json=record).status_code == 200
    response = client.post(
        '/v0/search/query',
        json={
            'query_id': 'q2',
            'actor_id': 'user-1',
            'text': 'evidence defaulting scope',
            'mode': 'HYBRID',
            'limit': 5,
            # no scope field -- this must not mean "disabled"
        },
    )
    assert response.status_code == 200
    academy_hits = [r for r in response.json()['results'] if r['source'] == 'ALEXANDRIAN_ACADEMY']
    assert len(academy_hits) == 1
    assert academy_hits[0]['result_id'] == 'lsr_default_scope_regression'
