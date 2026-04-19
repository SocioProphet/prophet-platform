from __future__ import annotations

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


def test_subject_http_missing(tmp_path):
    app_module = load_module('subject_readout.py', 'liberty_stack_subject_readout')
    client = TestClient(app_module.app)

    state_root = tmp_path / 'state'
    state_root.mkdir(parents=True, exist_ok=True)

    response = client.get('/v1/liberty-stack/by-subject', params={
        'state_root': str(state_root),
        'subject_ref': 'manifest://liberty-stack/demo/missing'
    })
    assert response.status_code == 404
