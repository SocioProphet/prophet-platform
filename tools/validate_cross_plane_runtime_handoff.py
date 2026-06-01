#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTPLANE_ALLOCATED = ROOT / "fixtures" / "external" / "agentplane" / "runtime-sandbox-run.allocated.valid.json"
SOCIOSPHERE_ALLOCATED = ROOT / "fixtures" / "external" / "sociosphere" / "runtime-evidence-ingestion.allocated.valid.json"
WORKROOM_VERIFIED = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.pre-merge-verified-receipt.valid.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def require_equal(label: str, left: Any, right: Any, problems: list[str]) -> None:
    if left != right:
        problems.append(f"{label}: {left!r} != {right!r}")


def require_contains(label: str, value: Any, values: list[Any], problems: list[str]) -> None:
    if value not in values:
        problems.append(f"{label}: {value!r} not found in {values!r}")


def validate(agentplane: dict[str, Any], sociosphere: dict[str, Any], workroom: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    agent_refs = sociosphere.get("agentplane_refs", {})
    workroom_sources = workroom.get("source_refs", {})
    workroom_evidence = workroom.get("evidence_packets", [])
    workroom_bde = workroom.get("behavioral_divergence_event", {})

    require_equal("runtime run ref AgentPlane->Sociosphere", agentplane.get("runtimeRunId"), agent_refs.get("runtime_run_ref"), problems)
    require_equal("environment ref AgentPlane->Sociosphere", agentplane.get("environmentRef"), agent_refs.get("environment_ref"), problems)
    require_equal("dependency graph ref AgentPlane->Sociosphere", agentplane.get("dependencyGraphRef"), agent_refs.get("dependency_graph_ref"), problems)
    require_equal("routing ref AgentPlane->Sociosphere", agentplane.get("routingRef"), agent_refs.get("routing_ref"), problems)
    require_equal("leak check ref AgentPlane->Sociosphere", agentplane.get("leakCheckRef"), agent_refs.get("leak_check_ref"), problems)

    for key in ("network", "async", "stateful"):
        require_equal(
            f"isolation {key} AgentPlane->Sociosphere",
            agentplane.get("isolationRefs", {}).get(key),
            agent_refs.get("isolation_refs", {}).get(key),
            problems,
        )

    for ref in agentplane.get("evidenceRefs", []):
        require_contains("evidence ref AgentPlane->Sociosphere", ref, agent_refs.get("evidence_refs", []), problems)
    for ref in agentplane.get("receiptRefs", []):
        require_contains("receipt ref AgentPlane->Sociosphere", ref, agent_refs.get("receipt_refs", []), problems)

    if sociosphere.get("state_write", {}).get("state_authority") != "Sociosphere":
        problems.append("Sociosphere fixture must retain Sociosphere state authority")
    if sociosphere.get("state_write", {}).get("execution_authority") != "AgentPlane":
        problems.append("Sociosphere fixture must retain AgentPlane execution authority")
    if sociosphere.get("state_write", {}).get("product_surface") != "Prophet Platform":
        problems.append("Sociosphere fixture must identify Prophet Platform as product surface")

    if sociosphere.get("runtime_parity", {}).get("level") != "runtime_observed":
        problems.append("allocated Sociosphere fixture must preserve runtime_observed evidence level")
    if sociosphere.get("runtime_parity", {}).get("certified") is not False:
        problems.append("allocated Sociosphere fixture must not certify full runtime parity")
    for gap in ("teardown_not_complete", "leak_check_not_complete"):
        if gap not in sociosphere.get("runtime_parity", {}).get("blocking_gaps", []):
            problems.append(f"allocated Sociosphere fixture must preserve blocking gap {gap}")

    # Workroom fixture currently models a Sociosphere SVF verified receipt, not the AgentPlane allocated runtime fixture.
    # The handoff invariant here is authority and claim-boundary compatibility, not identical receipt IDs yet.
    if workroom.get("runtime_parity_level") != "runtime_observed":
        problems.append("verified Workroom fixture must retain runtime_observed level")
    if workroom.get("validation_evidence_state") != "verified_receipt":
        problems.append("verified Workroom fixture must retain verified_receipt state")
    if workroom_bde.get("event_type") != "pre_merge_validation_verified":
        problems.append("verified Workroom fixture must use pre_merge_validation_verified event type")
    if workroom_bde.get("decision_state") != "resolved":
        problems.append("verified Workroom fixture must use resolved decision state")

    evidence_refs = {packet.get("evidence_ref") for packet in workroom_evidence if isinstance(packet, dict)}
    for ref in workroom_bde.get("evidence_refs", []):
        if ref not in evidence_refs:
            problems.append(f"Workroom BDE evidence ref missing from evidence packets: {ref}")

    receipt_packets = [packet for packet in workroom_evidence if packet.get("evidence_type") == "runtime_receipt"]
    if not receipt_packets:
        problems.append("verified Workroom fixture must include runtime_receipt evidence")
    for packet in receipt_packets:
        source_ref = packet.get("provenance", {}).get("source_ref")
        if source_ref != workroom_sources.get("validation_receipt_ref"):
            problems.append("Workroom runtime receipt provenance must match source_refs.validation_receipt_ref")

    return problems


def main() -> int:
    agentplane = load(AGENTPLANE_ALLOCATED)
    sociosphere = load(SOCIOSPHERE_ALLOCATED)
    workroom = load(WORKROOM_VERIFIED)
    problems = validate(agentplane, sociosphere, workroom)
    report = {
        "validator": "prophet-platform.cross-plane-runtime-handoff.validator.v1",
        "passed": not problems,
        "problems": problems,
        "inputs": {
            "agentplane": str(AGENTPLANE_ALLOCATED.relative_to(ROOT)),
            "sociosphere": str(SOCIOSPHERE_ALLOCATED.relative_to(ROOT)),
            "workroom": str(WORKROOM_VERIFIED.relative_to(ROOT)),
        },
        "non_claims": [
            "Validator checks fixture identity preservation and claim boundaries only.",
            "Validator does not execute sandbox infrastructure.",
            "Validator does not certify Signadot-style feature parity.",
            "Validator does not assert that AgentPlane allocated receipt and Sociosphere SVF receipt are the same receipt."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": cross-plane runtime handoff")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
