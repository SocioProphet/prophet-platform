from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_demo_transparent_telemetry_runtime(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["SOCIOPROFIT_STATE_HOME"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, "tools/demo_transparent_telemetry_runtime.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(proc.stdout)
    assert payload["service"] == "telemetry-runtime"
    assert payload["outcome"]["event"] == "reliability.conversation.stream.completed"
    assert payload["receipt"]["status"] == "recorded"
    assert payload["catalog_entry"]["service"] == "telemetry-runtime"
