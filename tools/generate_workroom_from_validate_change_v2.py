#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUEST = ROOT / "contracts" / "environment" / "validate-change-v2-request.example.json"
DEFAULT_RESPONSE = ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-observed.json"
DEFAULT_LINK = ROOT / "contracts" / "environment" / "validate-change-v2-agentplane-run-link.example.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def first_or_none(items: list[str]) -> str | None:
    return str(items[0]) if items else None


def evidence_state_to_parity(state: str) -> str:
    if state == "verified_receipt":
        return "runtime_observed"
    if state == "synthetic_observed":
        return "synthetic_observed"
    return "contract_only"


def change_set_ref(request: dict[str, Any], response: dict[str, Any]) -> str:
    repo = response.get("repo") or request.get("repo") or "unknown/repo"
    ref = request.get("ref") or response.get("request_id", "unknown-ref")
    return f"changeset://github/{repo}/{ref}"


def base_ids(state: str) -> dict[str, str]:
    slug = {
        "verified_receipt": "sociosphere-svf-verified",
        "missing_evidence": "scope-d-missing-evidence",
        "failed_receipt": "scope-d-failed-receipt",
        "stale_receipt": "scope-d-stale-receipt",
    }.get(state, f"scope-d-{state}")
    return {
        "slug": slug,
        "workroom_id": f"workroom:devsecops:pre-merge:{slug}",
        "event_id": f"bde:pre-merge-validation:{slug}",
        "claim_id": f"rca-claim:{slug}:validation-state",
        "grant_id": f"action-grant:{slug}:read-validation-evidence",
        "remediation_id": f"remediation-plan:{slug}:next-step",
        "regression_id": f"regression-fixture:{slug}:receipt-gate",
    }


def build_evidence_packet(state: str, evidence_ref: str, receipt_ref: str | None) -> dict[str, Any]:
    if state in {"verified_receipt", "failed_receipt", "stale_receipt"}:
        return {
            "evidence_ref": evidence_ref,
            "evidence_type": "runtime_receipt",
            "producer": "Sociosphere SVF local runner",
            "summary": "SVF receipt evidence was surfaced through validate_change v2 response fixtures.",
            "observed_at": "2026-05-31T18:46:09Z",
            "provenance": {
                "source_system": "Sociosphere",
                "source_ref": receipt_ref or "svf:receipt:missing",
                "collection_method": "fixture_mirrors_svf_local_receipt"
            },
            "non_claims": [
                "Receipt is fixture-scoped.",
                "Receipt does not certify container, browser, QEMU, cluster, or Signadot vendor parity."
            ]
        }
    return {
        "evidence_ref": evidence_ref,
        "evidence_type": "validation_result",
        "producer": "Prophet Platform validate_change v2 adapter",
        "summary": "Validation plans were selected but receipt-backed execution evidence is missing.",
        "observed_at": "2026-05-31T18:46:09Z",
        "provenance": {
            "source_system": "Prophet Platform",
            "source_ref": "validate-change-v2:missing-evidence",
            "collection_method": "fixture_response_mapping"
        },
        "non_claims": [
            "Missing evidence is validation debt, not validation success.",
            "No runtime parity is certified."
        ]
    }


def build_workroom(request: dict[str, Any], response: dict[str, Any], link: dict[str, Any]) -> dict[str, Any]:
    evidence_summary = response.get("evidence_summary", {})
    agentplane_execution = response.get("agentplane_execution", {})
    readiness = response.get("pr_readiness", {})
    selected_plans = response.get("selected_plans", []) or request.get("selected_plans", [])
    plan_ref = first_or_none(selected_plans) or "validation-plan://missing"

    state = str(evidence_summary.get("validation_evidence_state", "missing_evidence"))
    ids = base_ids(state)
    parity = evidence_state_to_parity(state)
    event_type = "pre_merge_validation_verified" if state == "verified_receipt" else "pre_merge_validation_failure"
    status = "resolved" if state == "verified_receipt" else "open"
    decision_state = "resolved" if state == "verified_receipt" else "blocked"
    claim_confidence = "high" if state == "verified_receipt" else "medium"

    receipt_ref = first_or_none(evidence_summary.get("receipt_refs", []))
    receipt_digest = first_or_none(evidence_summary.get("receipt_digests", []))
    evidence_ref = first_or_none(agentplane_execution.get("evidence_refs", []))
    if not evidence_ref:
        evidence_ref = f"evidence://prophet-platform/validate-change-v2/{ids['slug']}/missing-evidence"

    source_refs: dict[str, str] = {
        "change_set_ref": change_set_ref(request, response),
        "environment_request_ref": response.get("request_id", request.get("request_id")),
        "validation_run_ref": agentplane_execution.get("sandbox_run_ref", "agentplane:sandbox-run:missing"),
        "topology_ref": "topology://sociosphere/svf/local-dogfood",
    }
    if receipt_ref:
        source_refs["validation_receipt_ref"] = receipt_ref
    if receipt_digest:
        source_refs["validation_receipt_digest"] = receipt_digest

    if state == "verified_receipt":
        summary = "Fixture models a verified SVF local receipt for Sociosphere registry dogfood validation."
        claim_statement = "A Sociosphere SVF local receipt can be represented as runtime-observed validation evidence when the receipt reference is present and evidence provenance points to it."
        remediation_summary = "No code remediation is required for the verified receipt fixture."
        plan_status = "approved" if readiness.get("readiness_state") == "ready" else "candidate"
    elif state == "failed_receipt":
        summary = "Fixture models a failed receipt state that blocks PR readiness until repair and rerun."
        claim_statement = "Failed receipt evidence blocks validation success and requires repair before merge readiness can be claimed."
        remediation_summary = "Inspect failed receipt diagnostics, patch the failure, and rerun the selected validation plan."
        plan_status = "candidate"
    else:
        summary = "Fixture models selected validation plans without observed receipt-backed evidence."
        claim_statement = "Selected validation plans without observed evidence are validation debt, not validation success."
        remediation_summary = "Request or rerun AgentPlane validation until receipt-backed evidence is observed."
        plan_status = "candidate"

    return {
        "schema_version": "0.1.0",
        "workroom_id": ids["workroom_id"],
        "lane": "pre_merge_validation",
        "runtime_parity_level": parity,
        "validation_evidence_state": state,
        "source_refs": source_refs,
        "behavioral_divergence_event": {
            "event_id": ids["event_id"],
            "event_type": event_type,
            "source_lane": "pre_merge_validation",
            "status": status,
            "summary": summary,
            "environment_ref": "environment://local/sociosphere/svf",
            "topology_ref": source_refs["topology_ref"],
            "evidence_refs": [evidence_ref],
            "claim_refs": [ids["claim_id"]],
            "decision_state": decision_state,
            "non_claims": [
                "State is fixture-scoped.",
                "Fixture does not certify production readiness."
            ]
        },
        "evidence_packets": [build_evidence_packet(state, evidence_ref, receipt_ref)],
        "rca_claims": [
            {
                "claim_id": ids["claim_id"],
                "claim_status": "observation",
                "statement": claim_statement,
                "evidence_refs": [evidence_ref],
                "counterevidence_refs": [],
                "confidence": claim_confidence,
                "non_claims": [
                    "Observation is about fixture representation.",
                    "Observation does not authorize remediation."
                ]
            }
        ],
        "action_grants": [
            {
                "grant_id": ids["grant_id"],
                "action_class": "read_only",
                "status": "allowed",
                "scope": "Read validation response, receipt references, and evidence state for PR readiness.",
                "approval_required": False,
                "non_claims": [
                    "Grant permits read-only evidence inspection only.",
                    "Grant does not authorize execution."
                ]
            }
        ],
        "remediation_plans": [
            {
                "plan_id": ids["remediation_id"],
                "plan_status": plan_status,
                "risk_class": "read_only",
                "summary": remediation_summary,
                "evidence_refs": [evidence_ref],
                "required_action_grant_refs": [ids["grant_id"]],
                "non_claims": [
                    "Plan is fixture-scoped.",
                    "No production mutation is authorized."
                ]
            }
        ],
        "regression_fixtures": [
            {
                "fixture_id": ids["regression_id"],
                "fixture_status": "candidate",
                "derived_from": ids["event_id"],
                "summary": "Preserve a Workroom fixture that gates merge readiness on receipt-backed validation evidence.",
                "target_validation_plan_ref": plan_ref,
                "non_claims": [
                    "Fixture is not a live execution record.",
                    "Fixture does not replace Sociosphere or AgentPlane receipt verification."
                ]
            }
        ],
        "issued_at": "2026-05-31T18:47:00Z",
        "non_claims": [
            "This fixture models validate_change v2 response consumption only.",
            "This fixture does not execute SVF Actions.",
            "This fixture does not create or sign receipts."
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a DevSecOps Workroom record from validate_change v2 fixtures.")
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--response", type=Path, default=DEFAULT_RESPONSE)
    parser.add_argument("--observed", type=Path, help="Backward-compatible alias for --response")
    parser.add_argument("--link", type=Path, default=DEFAULT_LINK)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    response_path = args.observed or args.response
    record = build_workroom(load(args.request), load(response_path), load(args.link))
    payload = json.dumps(record, indent=2, sort_keys=False) + "\n"
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
