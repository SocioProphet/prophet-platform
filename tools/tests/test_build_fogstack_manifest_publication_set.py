from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_manifest_publication_set_attaches_optional_signatures(tmp_path: Path) -> None:
    manifest = tmp_path / 'fogstack.access-v0.1.manifest.json'
    manifest.write_text(json.dumps({
        'kind': 'FogStackBundleManifest',
        'schema_version': 'v0.1',
        'bundle_id': 'fogstack.access',
        'version': '0.1.0',
        'bundle': 'bundles/fogstack.access-v0.1.yaml',
        'rulepack': 'conformance/rulepacks/fogstack.access-v0.1.yaml',
        'bundle_digest': 'sha256:test',
        'rulepack_digest': 'sha256:test',
        'channel': 'preview',
        'support_state': 'community',
        'signed': False,
    }, indent=2) + '\n', encoding='utf-8')

    out_dir = tmp_path / 'publication'
    subprocess.run([
        sys.executable,
        'tools/build_fogstack_manifest_publication_set.py',
        '--output-dir', str(out_dir),
        '--manifest', str(manifest),
        '--signature-type', 'cosign',
        '--signature-ref-prefix', 'artifact://release',
    ], check=True)

    published = json.loads((out_dir / 'manifests' / manifest.name).read_text(encoding='utf-8'))
    assert published['signed'] is True
    assert published['signature']['type'] == 'cosign'
    assert published['signature']['ref'].endswith('fogstack.access-0.1.0.sig')

    index = json.loads((out_dir / 'manifest-publication-set.json').read_text(encoding='utf-8'))
    assert index['kind'] == 'FogStackManifestPublicationSet'
    assert len(index['manifests']) == 1
    assert index['manifests'][0]['bundle_id'] == 'fogstack.access'
