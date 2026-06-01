#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_workroom_from_validate_change_v2.py"
VALIDATOR = ROOT / "tools" / "validate_devsecops_workroom.py"
RESPONSES = {
    "requested": ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-requested.json",
    "observed": ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-observed.json",
    "failed": ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-failed.json",
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def generate_record(response_path: Path, out_path: Path) -> dict[str, Any]:
    subprocess.run(
        [sys.executable, str(GENERATOR), "--response", str(response_path), "--out", str(out_path)],
        check=True,
    )
    return load(out_path)


def build_bundle(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, Any]] = {}
    record_refs: dict[str, str] = {}

    for name, response_path in RESPONSES.items():
        record_path = out_dir / f"validate-change-v2-workroom.{name}.json"
        records[name] = generate_record(response_path, record_path)
        record_refs[name] = str(record_path.name)

    summary = {
        "bundle_id": "bundle:devsecops-workroom:validate-change-v2:fixture-states",
        "schema_version": "0.1.0",
        "source": "validate_change_v2_fixture_adapter",
        "record_refs": record_refs,
        "states": {
            name: {
                "workroom_id": record.get("workroom_id"),
                "runtime_parity_level": record.get("runtime_parity_level"),
                "validation_evidence_state": record.get("validation_evidence_state"),
                "event_type": record.get("behavioral_divergence_event", {}).get("event_type"),
                "decision_state": record.get("behavioral_divergence_event", {}).get("decision_state"),
            }
            for name, record in records.items()
        },
        "non_claims": [
            "Bundle is generated from fixtures only.",
            "Bundle does not execute live sandbox infrastructure.",
            "Bundle does not certify Signadot-style feature parity.",
            "Bundle does not authorize production remediation."
        ],
    }
    (out_dir / "validate-change-v2-workroom.bundle.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a validate_change v2 DevSecOps Workroom fixture bundle.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    summary = build_bundle(args.out)
    validator_result = subprocess.run([sys.executable, str(VALIDATOR)], text=True, capture_output=True)
    passed = validator_result.returncode == 0
    report = {
        "builder": "prophet-platform.validate-change-v2.workroom-bundle-builder.v1",
        "passed": passed,
        "summary": summary,
        "validator_stdout": validator_result.stdout,
        "validator_stderr": validator_result.stderr,
        "non_claims": [
            "Builder emits fixture artifacts only.",
            "Builder does not execute live sandbox infrastructure.",
            "Builder does not certify Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if passed else "FAIL") + ": validate_change v2 workroom bundle")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
