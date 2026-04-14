from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_fogstack_validation_to_evidence(tmp_path: Path):
    records = tmp_path / "artifacts"
    records.mkdir()
    (records / "fogstack.access.validation.record.json").write_text(json.dumps({
        "kind": "FogStackValidationRecord",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "validation_path": "tools/validate_fogstack.py",
        "source": "ci",
        "status": "executed",
        "summary": {"status": "pass", "exit_code": 0},
        "evidence_ref": "artifact://ci/fogstack.access.verify.json",
    }), encoding="utf-8")

    script = Path(__file__).resolve().parents[1] / "fogstack_validation_to_evidence.py"
    out = subprocess.run(
        [sys.executable, str(script), "--records-dir", str(records), "--state-root", str(tmp_path / "state"), "--service", "fogstack-validation"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(out.stdout)
    assert payload["count"] == 1
    p = tmp_path / "state" / "prophet-platform"
    assert (p / "payloads" / "fogstack-validation" / "fogstack_access-0.1.0.payload.json").exists()
    assert (p / "events" / "fogstack-validation" / "fogstack_access-0.1.0.event.json").exists()
    assert (p / "receipts" / "fogstack-validation" / "fogstack_access-0.1.0.receipt.json").exists()
    assert (p / "catalog" / "fogstack-validation" / "receipt_catalog.jsonl").exists()
