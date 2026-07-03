from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "tools" / "validate_autonomy_admission_receipt.py"
SCHEMA = REPO_ROOT / "contracts" / "AutonomyAdmissionReceipt.v0.1.json"
EXAMPLE = REPO_ROOT / "contracts" / "examples" / "autonomy-admission-receipt.json"


def _validate(receipt: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    p = tmp_path / "r.json"
    p.write_text(json.dumps(receipt), encoding="utf-8")
    return subprocess.run([sys.executable, str(VALIDATOR), str(p)], capture_output=True, text=True)


def test_example_validates(tmp_path: Path):
    proc = subprocess.run([sys.executable, str(VALIDATOR), str(EXAMPLE)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_granted_cannot_exceed_role_ceiling(tmp_path: Path):
    receipt = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    receipt["role_ceiling"] = "L0"
    receipt["granted_level"] = "L2"  # exceeds the ceiling
    proc = _validate(receipt, tmp_path)
    assert proc.returncode == 1
    assert "role_ceiling" in proc.stderr


def test_schema_rejects_malformed_gate_order():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    good = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    jsonschema.validate(good, schema)  # baseline: conforms
    for bad_order in (
        ["identity"] * 6,                                                  # duplicates
        ["audit", "revocation", "attestation", "evidence", "policy", "identity"],  # reversed
        ["identity", "policy", "evidence", "attestation", "revocation", "audit", "extra"],  # 7 items
    ):
        bad = dict(good)
        bad["trust_kernel_gate_order"] = bad_order
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
