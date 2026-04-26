from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def _write_policy(path: Path) -> None:
    path.write_text(
        'schema_version: "fogstack.manifest-promotion-policy/v0.1"\n'
        'kind: "FogStackManifestPromotionPolicy"\n'
        'defaults:\n'
        '  require_explicit_target_channel: true\n'
        '  require_explicit_target_support_state: true\n'
        'allowed_transitions:\n'
        '  preview:\n'
        '    community:\n'
        '      candidate:\n'
        '        - supported\n'
        '        - community\n',
        encoding='utf-8',
    )


def test_check_fogstack_manifest_promotion_policy_allows_valid_transition(tmp_path: Path) -> None:
    publication = tmp_path / 'manifest-publication-set.json'
    _write_json(publication, {
        'kind': 'FogStackManifestPublicationSet',
        'schema_version': 'v0.1',
        'promotion': {'channel': 'candidate', 'support_state': 'supported'},
        'manifests': [
            {
                'bundle_id': 'fogstack.access',
                'version': '0.1.0',
                'ref': 'manifests/fogstack.access-v0.1.manifest.json',
                'signed': False,
                'previous_channel': 'preview',
                'previous_support_state': 'community',
                'channel': 'candidate',
                'support_state': 'supported',
            }
        ],
    })
    policy = tmp_path / 'policy.yaml'
    _write_policy(policy)

    subprocess.run([
        sys.executable,
        'tools/check_fogstack_manifest_promotion_policy.py',
        '--publication-set', str(publication),
        '--policy-catalog', str(policy),
    ], check=True)


def test_check_fogstack_manifest_promotion_policy_rejects_invalid_transition(tmp_path: Path) -> None:
    publication = tmp_path / 'manifest-publication-set.json'
    _write_json(publication, {
        'kind': 'FogStackManifestPublicationSet',
        'schema_version': 'v0.1',
        'promotion': {'channel': 'stable', 'support_state': 'supported'},
        'manifests': [
            {
                'bundle_id': 'fogstack.access',
                'version': '0.1.0',
                'ref': 'manifests/fogstack.access-v0.1.manifest.json',
                'signed': False,
                'previous_channel': 'preview',
                'previous_support_state': 'community',
                'channel': 'stable',
                'support_state': 'supported',
            }
        ],
    })
    policy = tmp_path / 'policy.yaml'
    _write_policy(policy)

    proc = subprocess.run([
        sys.executable,
        'tools/check_fogstack_manifest_promotion_policy.py',
        '--publication-set', str(publication),
        '--policy-catalog', str(policy),
    ])
    assert proc.returncode != 0
