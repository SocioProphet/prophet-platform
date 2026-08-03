"""Contract + honesty tests for the dashboard-bff /v1/competitive-boards route.

Guards that the SERVING layer preserves the emitter's relative-only scoring model and its own honesty
gate: the route must reject (never silently serve) a board that fails
validate_intelligence_superiority_board.validate_board, and every cell it does serve must carry a
competitor_id declared on that category (no orphan cells), never an 'estate' pseudo-column (the whole
point of the relative-only redesign is that no such column exists)."""
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
    return TestClient(load_module('apps/dashboard-bff/main.py', 'dashboard_bff_main_ctb').app)


def test_route_returns_200_with_categories():
    data = _client().get('/v1/competitive-boards').json()
    assert data['service'] == 'dashboard-bff'
    assert len(data['categories']) >= 1
    assert data['generated_at']
    assert data['disclaimer']


def test_no_cell_references_an_undeclared_competitor_or_feature():
    data = _client().get('/v1/competitive-boards').json()
    for cat in data['categories']:
        comp_ids = {c['id'] for c in cat['competitors']}
        feat_ids = {f['id'] for f in cat['features']}
        for cell in cat['cells']:
            assert cell['competitor_id'] in comp_ids, (cat['id'], cell['competitor_id'])
            assert cell['feature_id'] in feat_ids, (cat['id'], cell['feature_id'])


def test_there_is_no_estate_pseudo_column():
    # The relative-only redesign's whole point: no competitor id/name is a stand-in for the estate.
    data = _client().get('/v1/competitive-boards').json()
    for cat in data['categories']:
        names = {c['name'].lower() for c in cat['competitors']}
        assert 'estate' not in names and 'socioprophet' not in names, cat['id']


def test_every_cell_carries_a_relative_verdict_and_self_assessed_basis():
    # No externally_certified cells exist in the current dataset — if one ever does, the schema/validator
    # require it to carry a cert_ref, but the route-level contract only promises the basis field survives.
    data = _client().get('/v1/competitive-boards').json()
    for cat in data['categories']:
        for cell in cat['cells']:
            assert cell['rank'] in ('BEAT', 'MEET', 'PARTIAL', 'GAP')
            assert cell['basis'] in ('self-assessed', 'externally-certified')


def test_beat_or_meet_cells_carry_evidence_or_are_explicitly_provisional():
    # Mirrors the emitter's own honesty discipline: a lead the route serves must be traceable.
    data = _client().get('/v1/competitive-boards').json()
    for cat in data['categories']:
        for cell in cat['cells']:
            if cell['rank'] in ('BEAT', 'MEET'):
                assert cell['evidence'] is not None or 'provisional' in (cell.get('note') or '').lower() \
                    or cell['maturity'] == 'spec', (cat['id'], cell['feature_id'], cell['competitor_id'])


def test_evidence_links_are_well_formed_github_urls_when_present():
    data = _client().get('/v1/competitive-boards').json()
    seen_any = False
    for cat in data['categories']:
        for cell in cat['cells']:
            ev = cell.get('evidence')
            if ev:
                seen_any = True
                assert ev['href'].startswith('https://github.com/SocioProphet/'), ev
                assert ev['label']
    assert seen_any, 'expected at least one cell with a resolvable evidence link'


def test_overview_lists_the_new_view():
    data = _client().get('/v1/overview').json()
    assert 'competitive-boards' in data['views']
