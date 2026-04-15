from __future__ import annotations

import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def load_module(relative_path: str, module_name: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_overview_contract():
    dashboard_module = load_module('apps/dashboard-bff/main.py', 'dashboard_bff_main')
    contracts_module = load_module('apps/dashboard-bff/contracts.py', 'dashboard_bff_contracts')
    client = TestClient(dashboard_module.app)
    response = client.get('/v1/overview')
    data = response.json()
    model = contracts_module.OverviewResponse(**data)
    assert model.service == 'dashboard-bff'
    assert isinstance(model.views, list)
    assert isinstance(model.trace_required, bool)
    assert isinstance(model.evidence_required, bool)
