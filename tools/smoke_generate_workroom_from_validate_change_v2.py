#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_workroom_from_validate_change_v2.py"
EXPECTED = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.pre-merge-verified-receipt.valid.json"
VALIDATOR = ROOT / "tools" / "validate_devsecops_workroom.py"


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def main() -> int:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "generated-workroom.json"
        subprocess.run([sys.executable, str(GENERATOR), "--out", str(out)], check=True)
        generated = load(out)
        expected = load(EXPECTED)

    if generated != expected:
        problems.append("generated workroom record does not match canonical verified receipt fixture")

    validator_result = subprocess.run([sys.executable, str(VALIDATOR)], text=True, capture_output=True)
    if validator_result.returncode != 0:
        problems.append("workroom validator failed after adapter generation")
        problems.append(validator_result.stdout)
        problems.append(validator_result.stderr)

    report = {
        "validator": "prophet-platform.validate-change-v2.workroom-adapter-smoke.v1",
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Smoke check validates deterministic fixture generation only.",
            "Smoke check does not execute live sandbox infrastructure.",
            "Smoke check does not certify Signadot-style feature parity."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": validate_change v2 workroom adapter smoke")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
