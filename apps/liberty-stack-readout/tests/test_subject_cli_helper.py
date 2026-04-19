from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_subject_cli(tmp_path):
    state_root = tmp_path / 'state'
    state_root.mkdir(parents=True, exist_ok=True)
    receipt = state_root / 'receipt-001.json'
    receipt.write_text(json.dumps({
        'status': 'succeeded',
        'action': 'validate_manifest',
        'subject_ref': 'manifest://liberty-stack/demo/0001',
        'evidence_bundle_ref': 'bundle://demo/0001'
    }), encoding='utf-8')

    output = subprocess.check_output(
        [
            sys.executable,
            'subject_cli.py',
            '--state-root',
            str(state_root),
            '--subject-ref',
            'manifest://liberty-stack/demo/0001',
        ],
        cwd=ROOT,
        text=True,
    )
    payload = json.loads(output)
    assert payload['action'] == 'validate_manifest'
    assert payload['status'] == 'succeeded'
    assert payload['subject_ref'] == 'manifest://liberty-stack/demo/0001'
