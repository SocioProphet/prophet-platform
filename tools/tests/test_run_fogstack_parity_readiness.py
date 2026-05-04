from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_fogstack_parity_readiness(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"
    proc = subprocess.run([
        sys.executable,
        "tools/run_fogstack_parity_readiness.py",
        "--output-dir", str(output_dir),
        "--summary",
    ], check=True, capture_output=True, text=True)
    assert "FogStack parity readiness: passed" in proc.stdout
    assert "Parity target: credible-mvp-ibm-style-parity" in proc.stdout
    assert "Turn counter: 31/32" in proc.stdout
    record_path = output_dir / "fogstack-parity-readiness.record.json"
    assert record_path.exists()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["kind"] == "FogStackParityReadinessRecord"
    assert record["status"] == "passed"
    assert record["errors"] == []
