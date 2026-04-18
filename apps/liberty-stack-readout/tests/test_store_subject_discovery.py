from __future__ import annotations

import json
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_subject_readout(tmp_path):
    store = load_module('store.py', 'liberty_stack_readout_store')
    state_root = tmp_path / 'state'
    state_root.mkdir(parents=True, exist_ok=True)

    receipt = state_root / 'receipt-001.json'
    receipt.write_text(json.dumps({
        'status': 'succeeded',
        'action': 'validate_manifest',
        'subject_ref': 'manifest://liberty-stack/demo/0001',
        'evidence_bundle_ref': 'bundle://demo/0001'
    }), encoding='utf-8')

    payload = store.build_subject_readout(str(state_root), 'manifest://liberty-stack/demo/0001')
    assert payload is not None
    assert payload['action'] == 'validate_manifest'
    assert payload['status'] == 'succeeded'
    assert payload['subject_ref'] == 'manifest://liberty-stack/demo/0001'
