from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_policy(path: Path) -> None:
    path.write_text(
        'schema_version: "fogstack.manifest-promotion-approver-policy/v0.1"\n'
        'kind: "FogStackManifestPromotionApproverPolicy"\n'
        'required_roles:\n'
        '  - "release-manager"\n'
        '  - "security-reviewer"\n'
        'approvers:\n'
        '  - id: "release-manager"\n'
        '    roles:\n'
        '      - "release-manager"\n'
        '  - id: "security-reviewer"\n'
        '    roles:\n'
        '      - "security-reviewer"\n',
        encoding="utf-8",
    )


def test_approver_policy_allows_required_roles(tmp_path: Path) -> None:
    approval = tmp_path / "approval.record.json"
    write_json(approval, {
        "approvals": [
            {"approver": "release-manager", "role": "release-manager"},
            {"approver": "security-reviewer", "role": "security-reviewer"},
        ]
    })
    policy = tmp_path / "approver-policy.yaml"
    write_policy(policy)
    subprocess.run([
        sys.executable,
        "tools/check_fogstack_manifest_promotion_approver_policy.py",
        "--approval-record", str(approval),
        "--approver-policy", str(policy),
    ], check=True)


def test_approver_policy_rejects_unknown_approver(tmp_path: Path) -> None:
    approval = tmp_path / "approval.record.json"
    write_json(approval, {
        "approvals": [
            {"approver": "unknown", "role": "release-manager"},
        ]
    })
    policy = tmp_path / "approver-policy.yaml"
    write_policy(policy)
    proc = subprocess.run([
        sys.executable,
        "tools/check_fogstack_manifest_promotion_approver_policy.py",
        "--approval-record", str(approval),
        "--approver-policy", str(policy),
    ])
    assert proc.returncode != 0
