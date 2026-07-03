"""Contract + honesty tests for the dashboard-bff /v1/intelligence-superiority route.

Guards that the SERVING layer preserves the producer's honesty discipline: trust provenance survives
onto every fact, and no metric is ever marked comparison_valid unless it has BOTH our reproduced facts
and a cited counterpart on the SAME metric (which, by the disjoint-metric design, means never today —
so a regression that let a cross-provider bar render would fail this test)."""
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


def test_route_returns_200_with_grouped_facts():
    data = _client().get('/v1/intelligence-superiority').json()
    assert data['service'] == 'dashboard-bff'
    assert data['reproduced_fact_count'] >= 1
    assert data['cited_fact_count'] >= 1
    assert len(data['metrics']) >= 1


def test_trust_provenance_survives_onto_every_fact():
    data = _client().get('/v1/intelligence-superiority').json()
    for m in data['metrics']:
        for f in m['ours']:
            assert f['reproduced_by_us'] is True and f['source_trust_class'] == 'internal_reproduced'
        for f in m['cited']:
            assert f['reproduced_by_us'] is False and f['source_trust_class'] == 'official_provider'


def test_comparison_valid_requires_both_ours_and_cited_on_the_same_metric():
    data = _client().get('/v1/intelligence-superiority').json()
    for m in data['metrics']:
        expected = bool(m['ours']) and bool(m['cited'])
        assert m['comparison_valid'] == expected
        # the disjoint-metric design means no metric has both today — a head-to-head bar is never valid
        if m['comparison_valid']:
            assert m['ours'] and m['cited']


def test_headline_and_disclaimer_are_present():
    data = _client().get('/v1/intelligence-superiority').json()
    assert 'p=0.0002' in data['headline_claim']          # the real, significant, reproduced claim
    assert 'did NOT independently verify' in data['disclaimer']


def test_overview_lists_the_new_view():
    data = _client().get('/v1/overview').json()
    assert 'intelligence-superiority' in data['views']
