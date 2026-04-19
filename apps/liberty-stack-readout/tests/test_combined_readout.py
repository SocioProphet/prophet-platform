from __future__ import annotations

import json
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_combined_readout_by_subject(tmp_path):
    app_module = load_module('combined_readout.py', 'liberty_stack_combined_readout')
    client = TestClient(app_module.app)

    state_root = tmp_path / 'state'
    state_root.mkdir(parents=True, exist_ok=True)
    receipt = state_root / 'receipt-001.json'
    receipt.write_text(json.dumps({
        'status': 'succeeded',
        'action': 'validate_manifest',
        'subject_ref': 'manifest://liberty-stack/demo/0001',
        'evidence_bundle_ref': 'bundle://demo/0001'
    }), encoding='utf-8')

    response = client.get('/v1/liberty-stack/readout', params={
        'state_root': str(state_root),
        'subject_ref': 'manifest://liberty-stack/demo/0001'
    })
    assert response.status_code == 200
    data = response.json()
    assert data['action'] == 'validate_manifest'
    assert data['status'] == 'succeeded'


def test_combined_readout_missing_args():
    app_module = load_module('combined_readout.py', 'liberty_stack_combined_readout_missing')
    client = TestClient(app_module.app)
    response = client.get('/v1/liberty-stack/readout')
    assert response.status_code == 400
