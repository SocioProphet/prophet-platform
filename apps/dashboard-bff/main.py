from fastapi import FastAPI
from apps.dashboard_bff.contracts import OverviewResponse

app = FastAPI(title='dashboard-bff')

@app.get('/health')
def health() -> dict:
    return {'service': 'dashboard-bff', 'status': 'ok'}

@app.get('/v1/overview', response_model=OverviewResponse)
def overview() -> OverviewResponse:
    return OverviewResponse(
        service='dashboard-bff',
        views=['overview', 'deepdive', 'cases'],
        trace_required=True,
        evidence_required=True,
    )
