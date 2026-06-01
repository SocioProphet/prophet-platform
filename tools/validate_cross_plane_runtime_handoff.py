#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTPLANE_ALLOCATED = ROOT / "fixtures" / "external" / "agentplane" / "runtime-sandbox-run.allocated.valid.json"
SOCIOSPHERE_ALLOCATED = ROOT / "fixtures" / "external" / "sociosphere" / "runtime-evidence-ingestion.allocated.valid.json"
WORKROOM_VERIFIED = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.pre-merge-verified-receipt.valid.json"
AGENTPLANE_SHARED = ROOT / "fixtures" / "external" / "agentplane" / "runtime-sandbox-run.shared-receipt.valid.json"
SOCIOSPHERE_SHARED = ROOT / "fixtures" / "external" / "sociosphere" / "runtime-evidence-ingestion.shared-receipt.valid.json"
WORKROOM_SHARED = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.shared-receipt.valid.json"


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


def validate_agentplane_to_sociosphere(agentplane: dict[str, Any], sociosphere: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    agent_refs = sociosphere.get("agentplane_refs", {})

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

    return problems


def validate_workroom_verified(workroom: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    workroom_sources = workroom.get("source_refs", {})
    workroom_evidence = workroom.get("evidence_packets", [])
    workroom_bde = workroom.get("behavioral_divergence_event", {})

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


def validate_compatibility_path(agentplane: dict[str, Any], sociosphere: dict[str, Any], workroom: dict[str, Any]) -> list[str]:
    problems = validate_agentplane_to_sociosphere(agentplane, sociosphere)
    problems.extend(validate_workroom_verified(workroom))
    return problems


def validate_shared_receipt_path(agentplane: dict[str, Any], sociosphere: dict[str, Any], workroom: dict[str, Any]) -> list[str]:
    problems = validate_agentplane_to_sociosphere(agentplane, sociosphere)
    problems.extend(validate_workroom_verified(workroom))

    agent_receipts = agentplane.get("receiptRefs", [])
    sociosphere_receipts = sociosphere.get("agentplane_refs", {}).get("receipt_refs", [])
    workroom_receipt = workroom.get("source_refs", {}).get("validation_receipt_ref")
    if not agent_receipts:
        problems.append("shared AgentPlane fixture must include receipt refs")
    else:
        require_contains("shared receipt AgentPlane->Sociosphere", agent_receipts[0], sociosphere_receipts, problems)
        require_equal("shared receipt AgentPlane->Workroom", agent_receipts[0], workroom_receipt, problems)

    workroom_run = workroom.get("source_refs", {}).get("validation_run_ref")
    require_equal("shared run AgentPlane->Workroom", agentplane.get("runtimeRunId"), workroom_run, problems)

    evidence_ref = (agentplane.get("evidenceRefs") or [None])[0]
    workroom_evidence_refs = {packet.get("evidence_ref") for packet in workroom.get("evidence_packets", []) if isinstance(packet, dict)}
    if evidence_ref not in workroom_evidence_refs:
        problems.append("shared evidence AgentPlane->Workroom evidence packet missing")

    for packet in workroom.get("evidence_packets", []):
        if packet.get("evidence_type") == "runtime_receipt":
            source_ref = packet.get("provenance", {}).get("source_ref")
            require_equal("shared receipt Workroom evidence provenance", source_ref, workroom_receipt, problems)

    return problems


def main() -> int:
    compatibility_inputs = {
        "agentplane": load(AGENTPLANE_ALLOCATED),
        "sociosphere": load(SOCIOSPHERE_ALLOCATED),
        "workroom": load(WORKROOM_VERIFIED),
    }
    shared_inputs = {
        "agentplane": load(AGENTPLANE_SHARED),
        "sociosphere": load(SOCIOSPHERE_SHARED),
        "workroom": load(WORKROOM_SHARED),
    }

    compatibility_problems = validate_compatibility_path(**compatibility_inputs)
    shared_problems = validate_shared_receipt_path(**shared_inputs)
    problems = compatibility_problems + shared_problems
    report = {
        "validator": "prophet-platform.cross-plane-runtime-handoff.validator.v1",
        "passed": not problems,
        "results": {
            "compatibility_path": compatibility_problems,
            "shared_receipt_path": shared_problems,
        },
        "inputs": {
            "compatibility_path": {
                "agentplane": str(AGENTPLANE_ALLOCATED.relative_to(ROOT)),
                "sociosphere": str(SOCIOSPHERE_ALLOCATED.relative_to(ROOT)),
                "workroom": str(WORKROOM_VERIFIED.relative_to(ROOT)),
            },
            "shared_receipt_path": {
                "agentplane": str(AGENTPLANE_SHARED.relative_to(ROOT)),
                "sociosphere": str(SOCIOSPHERE_SHARED.relative_to(ROOT)),
                "workroom": str(WORKROOM_SHARED.relative_to(ROOT)),
            },
        },
        "non_claims": [
            "Validator checks fixture identity preservation and claim boundaries only.",
            "Validator does not execute sandbox infrastructure.",
            "Validator does not certify Signadot-style feature parity.",
            "Shared receipt identity is fixture-scoped and does not imply full runtime feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": cross-plane runtime handoff")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
