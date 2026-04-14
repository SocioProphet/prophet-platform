from fastapi.testclient import TestClient
from apps.dashboard_bff.main import app
from apps.dashboard_bff.contracts import OverviewResponse


def test_overview_contract():
    client = TestClient(app)
    response = client.get('/v1/overview')
    data = response.json()
    model = OverviewResponse(**data)
    assert model.service == 'dashboard-bff'
    assert isinstance(model.views, list)
    assert isinstance(model.trace_required, bool)
    assert isinstance(model.evidence_required, bool)
