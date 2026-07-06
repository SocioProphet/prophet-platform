"""Contract + fidelity tests for the dashboard-bff /v1/vdt route.

Guards that the SERVING layer forwards the canonical economic-prophet engine's OUTPUT faithfully:
the driver×domain tensor sums to ~1.0, the served total equals the sum of the per-KPI contributions
(the endpoint recomputes nothing — a regression that recomputed or dropped a lever would fail here),
provenance survives so the number stays attributable to the engine + its input_hash, and the epistemic
status marks the figure synthetic rather than a measured business outcome."""
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


def _client():
    return TestClient(load_module('apps/dashboard-bff/main.py', 'dashboard_bff_main').app)


def test_route_returns_200_with_tensor_and_uplift():
    data = _client().get('/v1/vdt').json()
    assert data['service'] == 'dashboard-bff'
    assert data['industry'] == 'GICS45_SoftwarePlatforms'
    assert len(data['drivers']) == 6 and len(data['domains']) == 6
    assert len(data['weights']) == 36
    assert data['computed_total_value_uplift'] > 0


def test_catalog_lists_the_selectable_industries():
    data = _client().get('/v1/vdt/catalog').json()
    ids = {i['id'] for i in data['industries']}
    assert {'software', 'banks', 'energy', 'realestate', 'materials', 'consumerstaples'} <= ids
    for i in data['industries']:
        assert i['label'] and i['industry']


def test_new_industries_serve_complete_self_consistent_tensors():
    for vid, gics in (('realestate', 'GICS60_RealEstate'), ('materials', 'GICS15_Materials'),
                      ('consumerstaples', 'GICS30_ConsumerStaples')):
        v = _client().get(f'/v1/vdt?industry={vid}').json()
        assert v['industry'] == gics
        assert len(v['weights']) == 36
        assert abs(sum(c['weight'] for c in v['weights']) - 1.0) < 1e-6
        assert v['computed_total_value_uplift'] > 0


def test_industry_param_selects_a_different_tensor():
    software = _client().get('/v1/vdt?industry=software').json()
    banks = _client().get('/v1/vdt?industry=banks').json()
    assert banks['industry'] == 'GICS40_BanksDiversifiedFinancials'
    # a real, different attribution — the banks tensor is not the software one
    assert banks['industry'] != software['industry']
    assert abs(sum(c['weight'] for c in banks['weights']) - 1.0) < 1e-6


def test_unknown_industry_falls_back_to_software():
    data = _client().get('/v1/vdt?industry=not-a-real-industry').json()
    assert data['industry'] == 'GICS45_SoftwarePlatforms'


def test_tensor_is_a_complete_attribution_distribution():
    data = _client().get('/v1/vdt').json()
    assert abs(sum(c['weight'] for c in data['weights']) - 1.0) < 1e-6


def test_served_total_equals_sum_of_kpi_contributions():
    # the endpoint must forward the engine's numbers, not recompute — the served total has to be exactly
    # the sum of the per-KPI contributions it also serves.
    data = _client().get('/v1/vdt').json()
    kpi_sum = sum(k['value_contribution'] for k in data['per_kpi_contribution'])
    assert abs(data['computed_total_value_uplift'] - kpi_sum) < 1e-3
    # projected EV = baseline + uplift
    assert abs(data['projected_enterprise_value']
               - (data['enterprise_value_baseline'] + data['computed_total_value_uplift'])) < 1e-3


def test_per_driver_uplift_rolls_up_to_the_total():
    data = _client().get('/v1/vdt').json()
    assert abs(sum(data['per_driver_uplift'].values()) - data['computed_total_value_uplift']) < 1e-3


def test_provenance_and_epistemic_status_travel_with_the_payload():
    data = _client().get('/v1/vdt').json()
    prov = data['provenance']
    assert prov['source_repo'] == 'SocioProphet/economic-prophet'
    assert prov['input_hash']            # attributable to the engine's input
    assert 'regen' in prov               # regenerable, not hand-authored
    # the number is honestly framed as a synthetic, machine-checked illustration
    assert data['epistemic_status'].get('level') == 'synthetic'
    assert 'machine-checked measurement' in data['headline']
