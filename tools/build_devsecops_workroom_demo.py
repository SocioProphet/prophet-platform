#!/usr/bin/env python3
"""
DevSecOps Workroom Demo Bundle Generator.

Produces a self-contained demo bundle under build/devsecops-workroom-demo/ containing:

  - Workroom reports (JSON + Markdown) for the two primary lane scenarios:
      post_merge_incident  — production incident investigation
      pre_merge_validation — pre-merge validation failure
  - SCOPE-D adversarial validation summary
  - Per-contract fixture index covering all supporting contracts:
      ActionGrant, AgentPlane handoff/receipt, GAIA topology, blast-radius,
      PostmortemLesson, Alexandrian Academy canonization, regression promotion,
      investigation run
  - A signed manifest (manifest.json) listing every artifact with sha256 digest

Non-claims:
  - Demo bundle artifacts are evidence/fixture records only.
  - This tool does not execute remediation plans.
  - This tool does not issue action grants, receipts, or production authorizations.
  - This tool does not mutate workroom records or the Ontogenesis vocabulary.
  - Passing this demo does not constitute production readiness certification.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

WORKROOM_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "workroom"
GAIA_DIR = ROOT / "fixtures" / "external" / "gaia"

DEFAULT_OUT = ROOT / "build" / "devsecops-workroom-demo"

NON_CLAIMS = [
    "Demo bundle artifacts are evidence/fixture records only.",
    "This tool does not execute remediation plans.",
    "This tool does not issue action grants, receipts, or production authorizations.",
    "This tool does not mutate workroom records or the Ontogenesis vocabulary.",
    "Passing this demo does not constitute production readiness certification.",
]

# Primary workroom scenarios that produce full reports
WORKROOM_SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "post-merge-incident",
        "lane": "post_merge_incident",
        "description": "Post-merge production incident: elevated 5xx responses after deploy.",
        "workroom": WORKROOM_FIXTURES_DIR / "devsecops-workroom.post-merge-incident.valid.json",
        "gaia": GAIA_DIR / "workroom-post-merge-topology.valid.json",
        "guardrail_binding": WORKROOM_FIXTURES_DIR / "devsecops-workroom.guardrail-decision-binding.valid.json",
    },
    {
        "scenario_id": "pre-merge-validation-failure",
        "lane": "pre_merge_validation",
        "description": "Pre-merge validation failure: contract violation before promotion.",
        "workroom": WORKROOM_FIXTURES_DIR / "devsecops-workroom.pre-merge-validation-failure.valid.json",
        "gaia": GAIA_DIR / "workroom-post-merge-topology.valid.json",
        "guardrail_binding": WORKROOM_FIXTURES_DIR / "devsecops-workroom.guardrail-decision-binding.valid.json",
    },
]

# Supporting contract fixtures included in the fixture index
CONTRACT_FIXTURES: list[dict[str, str]] = [
    {
        "contract": "ActionGrant",
        "fixture": "devsecops-action-grant.read-only-allowed.valid.json",
        "description": "Read-only action grant — allowed, no approval required.",
    },
    {
        "contract": "AgentPlaneHandoff",
        "fixture": "devsecops-action-execution-handoff.approved.valid.json",
        "description": "AgentPlane execution handoff — approved_for_handoff status.",
    },
    {
        "contract": "AgentPlaneReceiptRef",
        "fixture": "devsecops-action-execution-receipt-ref.success.valid.json",
        "description": "AgentPlane execution receipt — success with artifact digest.",
    },
    {
        "contract": "TopologySnapshotRef",
        "fixture": "devsecops-topology-snapshot-ref.post-merge.valid.json",
        "description": "GAIA topology snapshot reference — post-merge scope.",
    },
    {
        "contract": "BlastRadiusEstimate",
        "fixture": "devsecops-blast-radius-estimate.topology-supported.valid.json",
        "description": "Blast-radius estimate — medium customer impact, topology-backed.",
    },
    {
        "contract": "InvestigationRun",
        "fixture": "devsecops-investigation-run.post-merge.valid.json",
        "description": "Investigation run — evidence collection plan and results.",
    },
    {
        "contract": "PostmortemLesson",
        "fixture": "devsecops-postmortem-lesson.accepted.valid.json",
        "description": "PostmortemLesson — accepted status with regression fixture refs.",
    },
    {
        "contract": "AcademyCanonicizationHandoff",
        "fixture": "devsecops-academy-canonization-handoff.submitted.valid.json",
        "description": "Alexandrian Academy canonization handoff — candidate submitted.",
    },
    {
        "contract": "RegressionPromotion",
        "fixture": "devsecops-regression-promotion.closed-loop.valid.json",
        "description": "Regression promotion — closed-loop: promoted fixture + active plan.",
    },
    {
        "contract": "ValidationRunReceiptRef",
        "fixture": "devsecops-validation-run-receipt-ref.svf.valid.json",
        "description": "Validation run receipt ref — SVF-issued, verified.",
    },
]

# SCOPE-D adversarial fixtures included in the bundle for documentation
ADVERSARIAL_FIXTURES: list[dict[str, str]] = [
    {
        "pattern": "rca_confidence_inflation",
        "fixture": "devsecops-workroom.scope-d-rca-confidence-inflation.adversarial.invalid.json",
        "description": "Confirmed causal claim with empty counterevidence_refs — rejected by SCOPE-D.",
    },
    {
        "pattern": "remediation_missing_non_execution_claim",
        "fixture": "devsecops-workroom.scope-d-remediation-missing-non-execution-claim.adversarial.invalid.json",
        "description": "Remediation plan omits non-execution non_claim — rejected by SCOPE-D.",
    },
    {
        "pattern": "prompt_injection_in_rca_statement",
        "fixture": "devsecops-workroom.scope-d-prompt-injection-in-rca-statement.adversarial.invalid.json",
        "description": "Prompt injection directive in RCA statement field — rejected by SCOPE-D.",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def artifact_entry(kind: str, path: Path, *, description: str = "") -> dict[str, Any]:
    return {
        "kind": kind,
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
        "description": description,
    }


def build_workroom_reports(out_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    reports_dir = out_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    for scenario in WORKROOM_SCENARIOS:
        sid = scenario["scenario_id"]
        scenario_out = reports_dir / sid
        scenario_out.mkdir(parents=True, exist_ok=True)

        run([
            sys.executable, "tools/build_devsecops_workroom_report.py",
            "--workroom", str(scenario["workroom"]),
            "--gaia", str(scenario["gaia"]),
            "--guardrail-binding", str(scenario["guardrail_binding"]),
            "--out", str(scenario_out),
        ])

        report_json = scenario_out / "devsecops-workroom-report.v0.1.json"
        report_md = scenario_out / "devsecops-workroom-report.v0.1.md"

        if report_json.exists():
            artifacts.append(artifact_entry(
                "WorkroomReport",
                report_json,
                description=f"JSON report: {scenario['description']}",
            ))
        if report_md.exists():
            artifacts.append(artifact_entry(
                "WorkroomReportMarkdown",
                report_md,
                description=f"Markdown report: {scenario['description']}",
            ))

    return artifacts


def build_scope_d_summary(out_dir: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "tools/validate_devsecops_scope_d_adversarial.py"],
        capture_output=True,
        text=True,
    )
    summary_path = out_dir / "scope-d-adversarial-summary.json"
    output_text = result.stdout.strip() or result.stderr.strip()
    try:
        summary_data = json.loads(output_text)
    except Exception:
        summary_data = {"raw": output_text, "returncode": result.returncode}
    summary_data["scope_d_exit_code"] = result.returncode
    summary_path.write_text(json.dumps(summary_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary_data


def build_fixture_index(out_dir: Path) -> list[dict[str, Any]]:
    index: list[dict[str, Any]] = []

    for entry in CONTRACT_FIXTURES:
        src = WORKROOM_FIXTURES_DIR / entry["fixture"]
        if not src.exists():
            print(f"  WARN: fixture not found, skipping: {src.name}", file=sys.stderr)
            continue
        index.append({
            "contract": entry["contract"],
            "fixture": entry["fixture"],
            "sha256": sha256_file(src),
            "description": entry["description"],
            "source_path": str(src.relative_to(ROOT)),
        })

    for entry in ADVERSARIAL_FIXTURES:
        src = WORKROOM_FIXTURES_DIR / entry["fixture"]
        if not src.exists():
            print(f"  WARN: adversarial fixture not found, skipping: {src.name}", file=sys.stderr)
            continue
        index.append({
            "contract": f"SCOPE-D:{entry['pattern']}",
            "fixture": entry["fixture"],
            "sha256": sha256_file(src),
            "description": entry["description"],
            "adversarial": True,
            "source_path": str(src.relative_to(ROOT)),
        })

    index_path = out_dir / "fixture-index.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Build DevSecOps Workroom demo bundle")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--issued-at", default=now_utc())
    args = parser.parse_args()

    out_dir: Path = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Building workroom scenario reports...")
    report_artifacts = build_workroom_reports(out_dir)

    print("Running SCOPE-D adversarial validation...")
    scope_d = build_scope_d_summary(out_dir)
    scope_d_path = out_dir / "scope-d-adversarial-summary.json"

    print("Building fixture index...")
    fixture_index = build_fixture_index(out_dir)

    # Manifest
    artifacts = list(report_artifacts)
    if scope_d_path.exists():
        artifacts.append(artifact_entry(
            "ScopeDAdversarialSummary",
            scope_d_path,
            description="SCOPE-D adversarial validation result for this demo bundle.",
        ))
    fixture_index_path = out_dir / "fixture-index.json"
    if fixture_index_path.exists():
        artifacts.append(artifact_entry(
            "FixtureIndex",
            fixture_index_path,
            description="Index of all workroom contract fixtures included in this bundle.",
        ))

    manifest: dict[str, Any] = {
        "manifestVersion": "0.1.0",
        "kind": "DevSecOpsWorkroomDemoManifest",
        "issuedAt": args.issued_at,
        "outputDir": str(out_dir.relative_to(ROOT)),
        "scenarios": [
            {
                "scenario_id": s["scenario_id"],
                "lane": s["lane"],
                "description": s["description"],
            }
            for s in WORKROOM_SCENARIOS
        ],
        "scopeD": {
            "valid": scope_d.get("valid"),
            "checked_valid": scope_d.get("checked_valid"),
            "checked_invalid": scope_d.get("checked_invalid"),
            "exit_code": scope_d.get("scope_d_exit_code"),
        },
        "fixtureCount": len(fixture_index),
        "artifacts": artifacts,
        "non_claims": NON_CLAIMS,
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if scope_d.get("scope_d_exit_code", 1) != 0:
        print(f"ERROR: SCOPE-D adversarial validation failed: {scope_d}", file=sys.stderr)
        return 1

    print(json.dumps({
        "ok": True,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "scenarioCount": len(WORKROOM_SCENARIOS),
        "artifactCount": len(artifacts),
        "fixtureIndexCount": len(fixture_index),
        "scopeDValid": scope_d.get("valid"),
        "non_claims": NON_CLAIMS,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
