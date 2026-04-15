from fastapi import FastAPI
from pathlib import Path
import importlib.util


def _load_overview_contract():
    path = Path(__file__).with_name('contracts.py')
    spec = importlib.util.spec_from_file_location('dashboard_bff_contracts', path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.OverviewResponse


OverviewResponse = _load_overview_contract()

app = FastAPI(title='dashboard-bff')

@app.get('/health')
def health() -> dict:
    return {'service': 'dashboard-bff', 'status': 'ok'}

@app.get('/v1/overview', response_model=OverviewResponse)
def overview() -> object:
    return OverviewResponse(
        service='dashboard-bff',
        views=['overview', 'deepdive', 'cases'],
        trace_required=True,
        evidence_required=True,
    )
