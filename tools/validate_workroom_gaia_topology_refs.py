#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKROOM = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.post-merge-incident.valid.json"
GAIA = ROOT / "fixtures" / "external" / "gaia" / "workroom-post-merge-topology.valid.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def main() -> int:
    problems: list[str] = []
    workroom = load(WORKROOM)
    gaia = load(GAIA)

    source_refs = workroom.get("source_refs", {})
    bde = workroom.get("behavioral_divergence_event", {})
    workroom_evidence = workroom.get("evidence_packets", [])
    gaia_evidence = gaia.get("source_evidence", [])

    topology_ref = source_refs.get("topology_ref")
    blast_radius_ref = source_refs.get("blast_radius_ref")
    if topology_ref != gaia.get("topology_ref"):
        problems.append("Workroom topology_ref must match GAIA topology_ref")
    if blast_radius_ref != gaia.get("blast_radius_ref"):
        problems.append("Workroom blast_radius_ref must match GAIA blast_radius_ref")
    if bde.get("topology_ref") != topology_ref:
        problems.append("Workroom BDE topology_ref must match source_refs.topology_ref")

    gaia_evidence_refs = {item.get("evidence_ref") for item in gaia_evidence if isinstance(item, dict)}
    workroom_topology_packets = [packet for packet in workroom_evidence if packet.get("evidence_type") == "topology_snapshot"]
    if not workroom_topology_packets:
        problems.append("Workroom incident must include topology_snapshot evidence")
    for packet in workroom_topology_packets:
        evidence_ref = packet.get("evidence_ref")
        if evidence_ref not in gaia_evidence_refs:
            problems.append(f"Workroom topology evidence {evidence_ref!r} missing from GAIA source_evidence")
        provenance = packet.get("provenance", {})
        if provenance.get("source_ref") != topology_ref:
            problems.append("Workroom topology evidence provenance.source_ref must match topology_ref")

    radius = gaia.get("blast_radius", {})
    if radius.get("radius_status") == "confirmed_by_observation":
        problems.append("GAIA mirror must not use confirmed_by_observation for this fixture")
    if radius.get("radius_status") not in {"candidate_only", "supported_by_topology"}:
        problems.append("GAIA radius_status is not allowed for fixture Workroom consumption")

    affected = set(radius.get("affected_node_refs", []))
    consumers = set(radius.get("candidate_consumer_refs", []))
    if "service://scope-d/api" not in affected:
        problems.append("GAIA blast radius must identify service://scope-d/api as affected fixture node")
    if not {"frontend://scope-d/checkout", "frontend://scope-d/account"}.issubset(consumers):
        problems.append("GAIA blast radius must preserve checkout/account candidate consumers")

    for claim in workroom.get("rca_claims", []):
        if claim.get("claim_status") == "confirmed_causal_claim":
            problems.append("Workroom fixture must not confirm RCA from topology alone")
    remediation = workroom.get("remediation_plans", [])
    for plan in remediation:
        if plan.get("plan_status") == "executed":
            problems.append("Workroom fixture must not execute remediation from topology fixture")

    report = {
        "validator": "prophet-platform.workroom-gaia-topology-refs.validator.v1",
        "passed": not problems,
        "problems": problems,
        "inputs": {
            "workroom": str(WORKROOM.relative_to(ROOT)),
            "gaia": str(GAIA.relative_to(ROOT)),
        },
        "non_claims": [
            "Validator checks Workroom-to-GAIA fixture references only.",
            "Validator does not execute runtime probes.",
            "Validator does not certify RCA causality.",
            "Validator does not authorize remediation.",
            "Validator does not certify Signadot feature parity."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom GAIA topology refs")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
