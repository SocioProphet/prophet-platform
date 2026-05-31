#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "contracts/computational-artifacts/prophet-artifact.v1alpha1.example.yaml"
VALIDATOR = ROOT / "tools/validate_prophet_artifact.py"
RUNNER = ROOT / "tools/run_prophet_artifact.py"
EXPECTED_FILES = {
    "run-record.json",
    "checksums.json",
    "validation-report.json",
    "benchmark-report.json",
    "sociosphere-registration.json",
    "sherlock-index-payload.json",
    "delivery-excellence-scoreboard-payload.json",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        output_dir = Path(td)

        validate = subprocess.run(
            [sys.executable, str(VALIDATOR), "--artifact", str(ARTIFACT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        run = subprocess.run(
            [sys.executable, str(RUNNER), "--artifact", str(ARTIFACT), "--output-dir", str(output_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        validation_payload = json.loads(validate.stdout)
        run_payload = json.loads(run.stdout)
        present = {path.name for path in output_dir.glob("*.json")}
        checks = {
            "validator_ok": validation_payload.get("ok") is True,
            "runner_ok": run_payload.get("ok") is True,
            "expected_outputs": EXPECTED_FILES <= present,
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "output_dir": str(output_dir)}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
