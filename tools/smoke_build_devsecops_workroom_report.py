#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_devsecops_workroom_report.py"
REQUIRED_REPORT_KEYS = {
    "report_id",
    "workroom",
    "event",
    "evidence",
    "rca_claims",
    "gaia_blast_radius",
    "action_grants",
    "guardrail_decision_bindings",
    "remediation_plans",
    "regression_fixtures",
    "non_claims",
}
REQUIRED_MARKDOWN_SECTIONS = [
    "# DevSecOps Workroom Report v0.1",
    "## Event",
    "## Evidence",
    "## RCA Claims",
    "## GAIA Blast Radius",
    "## Action Grants",
    "## Guardrail Decision Bindings",
    "## Remediation",
    "## Regression Fixtures",
    "## Non-claims",
]


def main() -> int:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report"
        result = subprocess.run([sys.executable, str(BUILDER), "--out", str(out)], text=True, capture_output=True)
        if result.returncode != 0:
            problems.append("report builder returned non-zero")
            problems.append(result.stdout)
            problems.append(result.stderr)
        json_path = out / "devsecops-workroom-report.v0.1.json"
        md_path = out / "devsecops-workroom-report.v0.1.md"
        if not json_path.exists():
            problems.append("JSON report was not generated")
            report = {}
        else:
            report = json.loads(json_path.read_text(encoding="utf-8"))
        if not md_path.exists():
            problems.append("Markdown report was not generated")
            markdown = ""
        else:
            markdown = md_path.read_text(encoding="utf-8")

    missing_keys = sorted(REQUIRED_REPORT_KEYS - set(report.keys())) if isinstance(report, dict) else sorted(REQUIRED_REPORT_KEYS)
    if missing_keys:
        problems.append(f"JSON report missing keys: {missing_keys}")

    if report:
        if report.get("workroom", {}).get("lane") != "post_merge_incident":
            problems.append("report workroom lane must be post_merge_incident")
        if report.get("gaia_blast_radius", {}).get("radius_status") not in {"candidate_only", "supported_by_topology"}:
            problems.append("report GAIA radius status must remain non-confirmed")
        for claim in report.get("rca_claims", []):
            if claim.get("claim_status") == "confirmed_causal_claim":
                problems.append("report must not contain confirmed causal claim for fixture incident")
        for plan in report.get("remediation_plans", []):
            if plan.get("plan_status") == "executed":
                problems.append("report must not contain executed remediation")
        non_claim_text = "\n".join(report.get("non_claims", [])).lower()
        for required in ("does not execute", "does not authorize remediation", "does not certify signadot"):
            if not all(word in non_claim_text for word in required.split()):
                problems.append(f"report non_claims missing {required!r} posture")

    for section in REQUIRED_MARKDOWN_SECTIONS:
        if section not in markdown:
            problems.append(f"Markdown report missing section {section!r}")

    result_report = {
        "validator": "prophet-platform.devsecops-workroom-report.smoke.v1",
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Smoke check validates fixture report generation only.",
            "Smoke check does not execute infrastructure.",
            "Smoke check does not inspect production systems.",
            "Smoke check does not authorize remediation.",
            "Smoke check does not certify Signadot feature parity."
        ]
    }
    print(json.dumps(result_report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": DevSecOps Workroom report smoke")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
