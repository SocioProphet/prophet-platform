from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_refresh_fogstack_manifest_digests_updates_placeholder_values(tmp_path: Path) -> None:
    bundle = tmp_path / 'bundle.yaml'
    bundle.write_text('kind: test\n', encoding='utf-8')

    rulepack = tmp_path / 'rulepack.yaml'
    rulepack.write_text('kind: rulepack\n', encoding='utf-8')

    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({
        'kind': 'FogStackBundleManifest',
        'schema_version': 'v0.1',
        'bundle_id': 'fogstack.test',
        'version': '0.1.0',
        'bundle': str(bundle),
        'rulepack': str(rulepack),
        'bundle_digest': 'sha256:PLACEHOLDER',
        'rulepack_digest': 'sha256:PLACEHOLDER',
        'channel': 'preview',
        'support_state': 'community',
        'signed': False,
    }, indent=2) + '\n', encoding='utf-8')

    subprocess.run([
        sys.executable,
        'tools/refresh_fogstack_manifest_digests.py',
        str(manifest),
    ], check=True)

    data = json.loads(manifest.read_text(encoding='utf-8'))
    assert data['bundle_digest'].startswith('sha256:')
    assert data['rulepack_digest'].startswith('sha256:')
    assert data['bundle_digest'] != 'sha256:PLACEHOLDER'
    assert data['rulepack_digest'] != 'sha256:PLACEHOLDER'
