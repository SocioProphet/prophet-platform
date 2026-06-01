#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_workroom_from_validate_change_v2.py"
EXPECTED_VERIFIED = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.pre-merge-verified-receipt.valid.json"
VALIDATOR = ROOT / "tools" / "validate_devsecops_workroom.py"
RESPONSES = {
    "requested": ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-requested.json",
    "observed": ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-observed.json",
    "failed": ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-failed.json",
}
EXPECTED_STATES = {
    "requested": ("contract_only", "missing_evidence", "pre_merge_validation_failure"),
    "observed": ("runtime_observed", "verified_receipt", "pre_merge_validation_verified"),
    "failed": ("contract_only", "failed_receipt", "pre_merge_validation_failure"),
}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def generate(response_path: Path, out: Path) -> dict:
    subprocess.run([
        sys.executable,
        str(GENERATOR),
        "--response",
        str(response_path),
        "--out",
        str(out),
    ], check=True)
    return load(out)


def main() -> int:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        generated_records: dict[str, dict] = {}
        for name, response_path in RESPONSES.items():
            generated_records[name] = generate(response_path, tmpdir / f"{name}.json")

    expected_verified = load(EXPECTED_VERIFIED)
    if generated_records["observed"] != expected_verified:
        problems.append("observed generated workroom record does not match canonical verified receipt fixture")

    for name, record in generated_records.items():
        expected_parity, expected_evidence_state, expected_event_type = EXPECTED_STATES[name]
        if record.get("runtime_parity_level") != expected_parity:
            problems.append(f"{name}: runtime_parity_level mismatch")
        if record.get("validation_evidence_state") != expected_evidence_state:
            problems.append(f"{name}: validation_evidence_state mismatch")
        event_type = record.get("behavioral_divergence_event", {}).get("event_type")
        if event_type != expected_event_type:
            problems.append(f"{name}: event_type mismatch")
        if name != "observed" and "validation_receipt_ref" in record.get("source_refs", {}) and name == "requested":
            problems.append("requested: missing-evidence record must not include validation_receipt_ref")

    validator_result = subprocess.run([sys.executable, str(VALIDATOR)], text=True, capture_output=True)
    if validator_result.returncode != 0:
        problems.append("workroom validator failed after adapter generation")
        problems.append(validator_result.stdout)
        problems.append(validator_result.stderr)

    report = {
        "validator": "prophet-platform.validate-change-v2.workroom-adapter-smoke.v1",
        "passed": not problems,
        "problems": problems,
        "validated_response_states": sorted(RESPONSES.keys()),
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
