#!/usr/bin/env python3
"""
Deterministic validator for a DevSecOps Workroom report.

Checks:
  - Report includes every evidence ref from the source workroom fixture.
  - Report includes every RCA claim from the source workroom fixture.
  - Report includes every remediation plan from the source workroom fixture.
  - Report includes every regression fixture from the source workroom fixture.
  - Report includes non_claims.
  - Report does not introduce unreferenced claims (no claim IDs absent from source).
  - Report preserves runtime_parity_level from source.
  - Report includes topology_ref and blast_radius_ref from source_refs.

Builds a fresh report internally and validates the on-disk report is consistent.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKROOM = (
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.post-merge-incident.valid.json"
)
DEFAULT_GAIA = ROOT / "fixtures" / "external" / "gaia" / "workroom-post-merge-topology.valid.json"
DEFAULT_GUARDRAIL_BINDING = (
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.guardrail-decision-binding.valid.json"
)
DEFAULT_REPORT = ROOT / "build" / "workroom-report" / "devsecops-workroom-report.v0.1.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def validate(
    workroom: dict[str, Any],
    report: dict[str, Any],
) -> list[str]:
    problems: list[str] = []

    # --- evidence completeness ---
    source_evidence_refs = {
        ep.get("evidence_ref")
        for ep in workroom.get("evidence_packets", [])
        if isinstance(ep, dict)
    }
    report_evidence_refs = {
        ep.get("evidence_ref")
        for ep in report.get("evidence", [])
        if isinstance(ep, dict)
    }
    for ref in sorted(source_evidence_refs - report_evidence_refs):
        problems.append(f"report is missing evidence ref: {ref!r}")

    # --- RCA claim completeness ---
    source_claim_ids = {
        c.get("claim_id")
        for c in workroom.get("rca_claims", [])
        if isinstance(c, dict)
    }
    report_claim_ids = {
        c.get("claim_id")
        for c in report.get("rca_claims", [])
        if isinstance(c, dict)
    }
    for cid in sorted(source_claim_ids - report_claim_ids):
        problems.append(f"report is missing RCA claim: {cid!r}")

    # --- no unreferenced claims introduced ---
    extra_claims = report_claim_ids - source_claim_ids
    for cid in sorted(extra_claims):
        problems.append(f"report introduces unknown RCA claim not in source: {cid!r}")

    # --- remediation plan completeness ---
    source_plan_ids = {
        p.get("plan_id")
        for p in workroom.get("remediation_plans", [])
        if isinstance(p, dict)
    }
    report_plan_ids = {
        p.get("plan_id")
        for p in report.get("remediation_plans", [])
        if isinstance(p, dict)
    }
    for pid in sorted(source_plan_ids - report_plan_ids):
        problems.append(f"report is missing remediation plan: {pid!r}")

    # --- regression fixture completeness ---
    source_fx_ids = {
        f.get("fixture_id")
        for f in workroom.get("regression_fixtures", [])
        if isinstance(f, dict)
    }
    report_fx_ids = {
        f.get("fixture_id")
        for f in report.get("regression_fixtures", [])
        if isinstance(f, dict)
    }
    for fid in sorted(source_fx_ids - report_fx_ids):
        problems.append(f"report is missing regression fixture: {fid!r}")

    # --- non_claims present ---
    if not report.get("non_claims"):
        problems.append("report is missing non_claims")

    # --- runtime parity level preserved ---
    source_parity = workroom.get("runtime_parity_level")
    report_parity = (report.get("workroom") or {}).get("runtime_parity_level")
    if source_parity and report_parity != source_parity:
        problems.append(
            f"report runtime_parity_level mismatch: source={source_parity!r}, report={report_parity!r}"
        )

    # --- topology_ref preserved ---
    source_topology = (workroom.get("source_refs") or {}).get("topology_ref")
    report_topology = (report.get("workroom") or {}).get("topology_ref")
    if source_topology and report_topology != source_topology:
        problems.append(
            f"report topology_ref mismatch: source={source_topology!r}, report={report_topology!r}"
        )

    # --- blast_radius_ref preserved ---
    source_blast = (workroom.get("source_refs") or {}).get("blast_radius_ref")
    report_blast = (report.get("workroom") or {}).get("blast_radius_ref")
    if source_blast and report_blast != source_blast:
        problems.append(
            f"report blast_radius_ref mismatch: source={source_blast!r}, report={report_blast!r}"
        )

    return problems


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate a DevSecOps Workroom report.")
    parser.add_argument("--workroom", type=Path, default=DEFAULT_WORKROOM)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    # Build the report first so the report file is fresh
    build_out = DEFAULT_REPORT.parent
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_devsecops_workroom_report.py"),
            "--workroom", str(args.workroom),
            "--out", str(build_out),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"FAIL: report builder failed:\n{result.stderr}")
        return 1

    workroom_data = load(args.workroom)
    report_path = build_out / "devsecops-workroom-report.v0.1.json"
    report_data = load(report_path)

    problems = validate(workroom_data, report_data)

    output = {
        "validator": "prophet-platform.devsecops-workroom-report.validator.v1",
        "passed": not problems,
        "problems": problems,
        "report_path": str(report_path.relative_to(ROOT)),
        "non_claims": [
            "Validator checks structural completeness and field preservation only.",
            "Validator does not execute infrastructure.",
            "Validator does not confirm RCA causality.",
            "Validator does not authorize remediation.",
        ],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": devsecops workroom report validator")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
