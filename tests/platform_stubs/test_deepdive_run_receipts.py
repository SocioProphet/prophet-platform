from __future__ import annotations

import importlib.util
import os
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


def test_deepdive_run_emits_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv('SOCIOPROFIT_STATE_HOME', str(tmp_path))
    monkeypatch.setenv('DEEPDIVE_ORCHESTRATOR_EMIT_RECEIPTS', '1')
    module = load_module('apps/deepdive-orchestrator/main.py', 'deepdive_orchestrator_main')
    client = TestClient(module.app)
    response = client.post('/v1/deepdive/run', json={
        'mode': 'repo_deepdive_report',
        'subject_ref': 'repo://SocioProphet/prophet-platform',
        'prompt': 'find the main issue',
    })
    data = response.json()
    assert response.status_code == 200
    assert data['service'] == 'deepdive-orchestrator'
    assert data['mode'] == 'repo_deepdive_report'
    assert 'X-Payload-Ref' in response.headers
    assert 'X-Evidence-Receipt-Ref' in response.headers
