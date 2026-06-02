#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKROOM = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.post-merge-incident.valid.json"
DEFAULT_GAIA = ROOT / "fixtures" / "external" / "gaia" / "workroom-post-merge-topology.valid.json"
DEFAULT_GUARDRAIL_BINDING = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.guardrail-decision-binding.valid.json"
DEFAULT_OUT = ROOT / "build" / "workroom-report"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def bullet(items: list[str]) -> str:
    if not items:
        return "- None recorded."
    return "\n".join(f"- {item}" for item in items)


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "No rows."
    header = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |" for row in rows)
    return "\n".join([header, sep, body])


def build_report(workroom: dict[str, Any], gaia: dict[str, Any], guardrail: dict[str, Any]) -> dict[str, Any]:
    bde = workroom.get("behavioral_divergence_event", {})
    source_refs = workroom.get("source_refs", {})
    evidence = workroom.get("evidence_packets", [])
    claims = workroom.get("rca_claims", [])
    grants = workroom.get("action_grants", [])
    plans = workroom.get("remediation_plans", [])
    regressions = workroom.get("regression_fixtures", [])
    blast_radius = gaia.get("blast_radius", {})

    return {
        "report_id": f"report:{workroom.get('workroom_id')}",
        "schema_version": "0.1.0",
        "workroom": {
            "workroom_id": workroom.get("workroom_id"),
            "lane": workroom.get("lane"),
            "runtime_parity_level": workroom.get("runtime_parity_level"),
            "incident_ref": source_refs.get("incident_ref"),
            "investigation_run_ref": source_refs.get("investigation_run_ref"),
            "topology_ref": source_refs.get("topology_ref"),
            "blast_radius_ref": source_refs.get("blast_radius_ref"),
        },
        "event": {
            "event_id": bde.get("event_id"),
            "event_type": bde.get("event_type"),
            "status": bde.get("status"),
            "decision_state": bde.get("decision_state"),
            "summary": bde.get("summary"),
        },
        "evidence": [
            {
                "evidence_ref": item.get("evidence_ref"),
                "evidence_type": item.get("evidence_type"),
                "producer": item.get("producer"),
                "summary": item.get("summary"),
                "source_ref": item.get("provenance", {}).get("source_ref"),
            }
            for item in evidence
        ],
        "rca_claims": [
            {
                "claim_id": item.get("claim_id"),
                "claim_status": item.get("claim_status"),
                "confidence": item.get("confidence"),
                "statement": item.get("statement"),
                "evidence_refs": item.get("evidence_refs", []),
                "counterevidence_refs": item.get("counterevidence_refs", []),
            }
            for item in claims
        ],
        "gaia_blast_radius": {
            "topology_ref": gaia.get("topology_ref"),
            "blast_radius_ref": gaia.get("blast_radius_ref"),
            "radius_status": blast_radius.get("radius_status"),
            "affected_node_refs": blast_radius.get("affected_node_refs", []),
            "candidate_consumer_refs": blast_radius.get("candidate_consumer_refs", []),
            "impact_hypotheses": blast_radius.get("impact_hypotheses", []),
            "confidence": blast_radius.get("confidence"),
        },
        "action_grants": [
            {
                "grant_id": item.get("grant_id"),
                "action_class": item.get("action_class"),
                "status": item.get("status"),
                "approval_required": item.get("approval_required"),
                "scope": item.get("scope"),
            }
            for item in grants
        ],
        "guardrail_decision_bindings": {
            "binding_id": guardrail.get("binding_id"),
            "action_grant_bindings": guardrail.get("action_grant_bindings", []),
            "remediation_bindings": guardrail.get("remediation_bindings", []),
        },
        "remediation_plans": [
            {
                "plan_id": item.get("plan_id"),
                "plan_status": item.get("plan_status"),
                "risk_class": item.get("risk_class"),
                "summary": item.get("summary"),
                "required_action_grant_refs": item.get("required_action_grant_refs", []),
            }
            for item in plans
        ],
        "regression_fixtures": [
            {
                "fixture_id": item.get("fixture_id"),
                "fixture_status": item.get("fixture_status"),
                "summary": item.get("summary"),
                "target_validation_plan_ref": item.get("target_validation_plan_ref"),
            }
            for item in regressions
        ],
        "non_claims": [
            "Report is generated from fixture records only.",
            "Report does not execute infrastructure.",
            "Report does not inspect production systems.",
            "Report does not confirm RCA causality.",
            "Report does not authorize remediation.",
            "Report does not certify Signadot feature parity."
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    workroom = report["workroom"]
    event = report["event"]
    blast = report["gaia_blast_radius"]

    lines: list[str] = []
    lines.append(f"# DevSecOps Workroom Report v0.1")
    lines.append("")
    lines.append(f"Report: `{report['report_id']}`")
    lines.append(f"Workroom: `{workroom['workroom_id']}`")
    lines.append("")
    lines.append("## Event")
    lines.append("")
    lines.append(table(
        ["Field", "Value"],
        [
            ["Lane", workroom.get("lane")],
            ["Runtime parity level", workroom.get("runtime_parity_level")],
            ["Incident", workroom.get("incident_ref")],
            ["Event type", event.get("event_type")],
            ["Status", event.get("status")],
            ["Decision state", event.get("decision_state")],
            ["Summary", event.get("summary")],
        ],
    ))
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    lines.append(table(
        ["Type", "Evidence ref", "Producer", "Summary"],
        [[item["evidence_type"], item["evidence_ref"], item["producer"], item["summary"]] for item in report["evidence"]],
    ))
    lines.append("")
    lines.append("## RCA Claims")
    lines.append("")
    lines.append(table(
        ["Status", "Confidence", "Claim", "Statement"],
        [[item["claim_status"], item["confidence"], item["claim_id"], item["statement"]] for item in report["rca_claims"]],
    ))
    lines.append("")
    lines.append("## GAIA Blast Radius")
    lines.append("")
    lines.append(table(
        ["Field", "Value"],
        [
            ["Topology ref", blast.get("topology_ref")],
            ["Blast-radius ref", blast.get("blast_radius_ref")],
            ["Radius status", blast.get("radius_status")],
            ["Affected nodes", ", ".join(blast.get("affected_node_refs", []))],
            ["Candidate consumers", ", ".join(blast.get("candidate_consumer_refs", []))],
            ["Confidence", blast.get("confidence")],
        ],
    ))
    lines.append("")
    lines.append("Impact hypotheses:")
    lines.append(bullet(blast.get("impact_hypotheses", [])))
    lines.append("")
    lines.append("## Action Grants")
    lines.append("")
    lines.append(table(
        ["Action class", "Status", "Approval required", "Grant", "Scope"],
        [[item["action_class"], item["status"], str(item["approval_required"]), item["grant_id"], item["scope"]] for item in report["action_grants"]],
    ))
    lines.append("")
    lines.append("## Guardrail Decision Bindings")
    lines.append("")
    grant_bindings = report["guardrail_decision_bindings"].get("action_grant_bindings", [])
    lines.append(table(
        ["Grant", "Guardrail fixture", "Expected decision", "Binding status"],
        [[item["grant_ref"], item["guardrail_fixture_ref"], item["guardrail_expected_decision"], item["binding_status"]] for item in grant_bindings],
    ))
    lines.append("")
    lines.append("## Remediation")
    lines.append("")
    lines.append(table(
        ["Risk", "Status", "Plan", "Summary"],
        [[item["risk_class"], item["plan_status"], item["plan_id"], item["summary"]] for item in report["remediation_plans"]],
    ))
    lines.append("")
    lines.append("## Regression Fixtures")
    lines.append("")
    lines.append(table(
        ["Status", "Fixture", "Target validation plan", "Summary"],
        [[item["fixture_status"], item["fixture_id"], item["target_validation_plan_ref"], item["summary"]] for item in report["regression_fixtures"]],
    ))
    lines.append("")
    lines.append("## Non-claims")
    lines.append("")
    lines.append(bullet(report["non_claims"]))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a DevSecOps Workroom report from fixture records.")
    parser.add_argument("--workroom", type=Path, default=DEFAULT_WORKROOM)
    parser.add_argument("--gaia", type=Path, default=DEFAULT_GAIA)
    parser.add_argument("--guardrail-binding", type=Path, default=DEFAULT_GUARDRAIL_BINDING)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report(load(args.workroom), load(args.gaia), load(args.guardrail_binding))
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "devsecops-workroom-report.v0.1.json"
    md_path = args.out / "devsecops-workroom-report.v0.1.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({
        "builder": "prophet-platform.devsecops-workroom-report.builder.v1",
        "passed": True,
        "outputs": [str(json_path), str(md_path)],
        "non_claims": report["non_claims"],
    }, indent=2, sort_keys=True))
    print("PASS: DevSecOps Workroom report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
