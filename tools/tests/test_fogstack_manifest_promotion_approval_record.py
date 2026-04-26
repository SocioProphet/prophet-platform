from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def test_emit_and_check_signed_promotion_approval_record(tmp_path: Path) -> None:
    promotion_set = tmp_path / 'manifest-publication-set.json'
    _write_json(promotion_set, {
        'kind': 'FogStackManifestPublicationSet',
        'schema_version': 'v0.1',
        'promotion': {'channel': 'candidate', 'support_state': 'supported'},
        'manifests': [],
    })

    approval = tmp_path / 'approval.record.json'
    subprocess.run([
        sys.executable,
        'tools/emit_fogstack_manifest_promotion_approval_record.py',
        '--promotion-set', str(promotion_set),
        '--required-approvals', '2',
        '--approval', 'alice:release-manager:approved candidate promotion',
        '--approval', 'bob:security-reviewer:approved release evidence',
        '--signature-type', 'other',
        '--signature-ref', 'artifact://release/fogstack.promotion.approval.sig',
        '--output', str(approval),
    ], check=True)

    record = json.loads(approval.read_text(encoding='utf-8'))
    assert record['kind'] == 'FogStackManifestPromotionApprovalRecord'
    assert record['status'] == 'approved'
    assert record['signed'] is True
    assert len(record['approvals']) == 2
    assert record['target_channel'] == 'candidate'
    assert record['target_support_state'] == 'supported'

    subprocess.run([
        sys.executable,
        'tools/check_fogstack_manifest_promotion_approval_record.py',
        '--approval-record', str(approval),
        '--promotion-set', str(promotion_set),
        '--require-signed',
    ], check=True)


def test_check_promotion_approval_record_rejects_unsigned_when_required(tmp_path: Path) -> None:
    promotion_set = tmp_path / 'manifest-publication-set.json'
    _write_json(promotion_set, {
        'kind': 'FogStackManifestPublicationSet',
        'schema_version': 'v0.1',
        'promotion': {'channel': 'candidate', 'support_state': 'supported'},
        'manifests': [],
    })

    approval = tmp_path / 'approval.record.json'
    subprocess.run([
        sys.executable,
        'tools/emit_fogstack_manifest_promotion_approval_record.py',
        '--promotion-set', str(promotion_set),
        '--required-approvals', '1',
        '--approval', 'alice:release-manager:approved',
        '--output', str(approval),
    ], check=True)

    proc = subprocess.run([
        sys.executable,
        'tools/check_fogstack_manifest_promotion_approval_record.py',
        '--approval-record', str(approval),
        '--promotion-set', str(promotion_set),
        '--require-signed',
    ])
    assert proc.returncode != 0


def test_check_promotion_approval_record_rejects_digest_mismatch(tmp_path: Path) -> None:
    promotion_set = tmp_path / 'manifest-publication-set.json'
    _write_json(promotion_set, {
        'kind': 'FogStackManifestPublicationSet',
        'schema_version': 'v0.1',
        'promotion': {'channel': 'candidate', 'support_state': 'supported'},
        'manifests': [],
    })

    approval = tmp_path / 'approval.record.json'
    subprocess.run([
        sys.executable,
        'tools/emit_fogstack_manifest_promotion_approval_record.py',
        '--promotion-set', str(promotion_set),
        '--required-approvals', '1',
        '--approval', 'alice:release-manager:approved',
        '--signature-type', 'other',
        '--signature-ref', 'artifact://release/fogstack.promotion.approval.sig',
        '--output', str(approval),
    ], check=True)

    _write_json(promotion_set, {
        'kind': 'FogStackManifestPublicationSet',
        'schema_version': 'v0.1',
        'promotion': {'channel': 'stable', 'support_state': 'supported'},
        'manifests': [],
    })

    proc = subprocess.run([
        sys.executable,
        'tools/check_fogstack_manifest_promotion_approval_record.py',
        '--approval-record', str(approval),
        '--promotion-set', str(promotion_set),
        '--require-signed',
    ])
    assert proc.returncode != 0
