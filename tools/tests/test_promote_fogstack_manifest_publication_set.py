from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_promote_fogstack_manifest_publication_set_updates_channel_and_support_state(tmp_path: Path) -> None:
    input_dir = tmp_path / 'input'
    manifests_dir = input_dir / 'manifests'
    manifests_dir.mkdir(parents=True)

    manifest = manifests_dir / 'fogstack.access-v0.1.manifest.json'
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

    (input_dir / 'manifest-publication-set.json').write_text(json.dumps({
        'kind': 'FogStackManifestPublicationSet',
        'schema_version': 'v0.1',
        'manifests': [
            {
                'bundle_id': 'fogstack.access',
                'version': '0.1.0',
                'ref': str(manifest),
                'signed': False,
            }
        ],
    }, indent=2) + '\n', encoding='utf-8')

    catalog = tmp_path / 'support.yaml'
    catalog.write_text(
        'schema_version: "fogstack.support-state/v0.1"\n'
        'kind: "FogStackSupportStates"\n'
        'offerings:\n'
        '  - bundle_id: "fogstack.access"\n'
        '    version: "0.1.0"\n'
        '    channel: "preview"\n'
        '    support_state: "community"\n'
        '    lifecycle_status: "merged-upstream"\n',
        encoding='utf-8',
    )

    output_dir = tmp_path / 'output'
    subprocess.run([
        sys.executable,
        'tools/promote_fogstack_manifest_publication_set.py',
        '--input-dir', str(input_dir),
        '--output-dir', str(output_dir),
        '--support-catalog', str(catalog),
        '--target-channel', 'candidate',
        '--target-support-state', 'supported',
    ], check=True)

    promoted_manifest = json.loads((output_dir / 'manifests' / manifest.name).read_text(encoding='utf-8'))
    assert promoted_manifest['channel'] == 'candidate'
    assert promoted_manifest['support_state'] == 'supported'

    promoted_index = json.loads((output_dir / 'manifest-publication-set.json').read_text(encoding='utf-8'))
    assert promoted_index['promotion']['channel'] == 'candidate'
    assert promoted_index['promotion']['support_state'] == 'supported'
    assert promoted_index['manifests'][0]['lifecycle_status'] == 'merged-upstream'
