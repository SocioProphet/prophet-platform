#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUEST = ROOT / "contracts" / "environment" / "validate-change-v2-request.example.json"
DEFAULT_OBSERVED = ROOT / "contracts" / "environment" / "validate-change-v2-response.environment-observed.json"
DEFAULT_LINK = ROOT / "contracts" / "environment" / "validate-change-v2-agentplane-run-link.example.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def first(items: list[str], label: str) -> str:
    if not items:
        raise ValueError(f"missing {label}")
    return str(items[0])


def build_workroom(request: dict[str, Any], observed: dict[str, Any], link: dict[str, Any]) -> dict[str, Any]:
    evidence_summary = observed.get("evidence_summary", {})
    agentplane_execution = observed.get("agentplane_execution", {})
    evidence_refs = agentplane_execution.get("evidence_refs", [])
    receipt_refs = evidence_summary.get("receipt_refs", [])
    receipt_digests = evidence_summary.get("receipt_digests", [])
    selected_plans = observed.get("selected_plans", []) or request.get("selected_plans", [])
    repo = observed.get("repo") or request.get("repo")
    readiness = observed.get("pr_readiness", {})
    environment = observed.get("environment", {}) or request.get("environment_request", {})

    receipt_ref = first(receipt_refs, "receipt refs")
    receipt_digest = first(receipt_digests, "receipt digests")
    evidence_ref = first(evidence_refs, "evidence refs")
    plan_ref = first(selected_plans, "selected plans")

    workroom_id = "workroom:devsecops:pre-merge:sociosphere-svf-verified"
    event_id = "bde:pre-merge-validation-success:sociosphere-svf"
    claim_id = "rca-claim:sociosphere-svf:receipt-observed"
    action_grant_id = "action-grant:sociosphere-svf:read-receipt"
    remediation_id = "remediation-plan:sociosphere-svf:none-required"
    regression_fixture_id = "regression-fixture:sociosphere-svf:receipt-gate"
    topology_ref = "topology://sociosphere/svf/local-dogfood"

    request_repo = str(repo or "unknown").replace("/", "/")
    change_set_ref = "changeset://github/SocioProphet/sociosphere/pull/434"
    if request_repo and request.get("ref"):
        change_set_ref = f"changeset://github/{request_repo}/{request.get('ref')}"

    return {
        "schema_version": "0.1.0",
        "workroom_id": workroom_id,
        "lane": "pre_merge_validation",
        "runtime_parity_level": "runtime_observed",
        "validation_evidence_state": evidence_summary.get("validation_evidence_state", "verified_receipt"),
        "source_refs": {
            "change_set_ref": change_set_ref,
            "environment_request_ref": observed.get("request_id", request.get("request_id")),
            "validation_run_ref": agentplane_execution.get("sandbox_run_ref"),
            "validation_receipt_ref": receipt_ref,
            "validation_receipt_digest": receipt_digest,
            "topology_ref": topology_ref
        },
        "behavioral_divergence_event": {
            "event_id": event_id,
            "event_type": "pre_merge_validation_verified",
            "source_lane": "pre_merge_validation",
            "status": "resolved",
            "summary": "Fixture models a verified SVF local receipt for Sociosphere registry dogfood validation.",
            "environment_ref": "environment://local/sociosphere/svf",
            "topology_ref": topology_ref,
            "evidence_refs": [evidence_ref],
            "claim_refs": [claim_id],
            "decision_state": "resolved",
            "non_claims": [
                "Resolved state is fixture-scoped.",
                "Fixture does not certify production readiness."
            ]
        },
        "evidence_packets": [
            {
                "evidence_ref": evidence_ref,
                "evidence_type": "runtime_receipt",
                "producer": "Sociosphere SVF local runner",
                "summary": "Verified local SVF receipt for registered Action execution and receipt digest verification.",
                "observed_at": "2026-05-31T18:46:09Z",
                "provenance": {
                    "source_system": "Sociosphere",
                    "source_ref": receipt_ref,
                    "collection_method": "fixture_mirrors_svf_local_receipt"
                },
                "non_claims": [
                    "Receipt is local-only.",
                    "Receipt does not certify container, browser, QEMU, cluster, or Signadot vendor parity."
                ]
            }
        ],
        "rca_claims": [
            {
                "claim_id": claim_id,
                "claim_status": "observation",
                "statement": "A Sociosphere SVF local receipt can be represented as runtime-observed validation evidence when the receipt reference is present and evidence provenance points to it.",
                "evidence_refs": [evidence_ref],
                "counterevidence_refs": [],
                "confidence": "high",
                "non_claims": [
                    "Observation is about fixture representation.",
                    "Observation does not authorize remediation."
                ]
            }
        ],
        "action_grants": [
            {
                "grant_id": action_grant_id,
                "action_class": "read_only",
                "status": "allowed",
                "scope": "Read SVF receipt references and validation evidence for PR readiness.",
                "approval_required": False,
                "non_claims": [
                    "Grant permits read-only receipt inspection only.",
                    "Grant does not authorize execution."
                ]
            }
        ],
        "remediation_plans": [
            {
                "plan_id": remediation_id,
                "plan_status": "approved" if readiness.get("readiness_state") == "ready" else "candidate",
                "risk_class": "read_only",
                "summary": "No code remediation is required for the verified receipt fixture.",
                "evidence_refs": [evidence_ref],
                "required_action_grant_refs": [action_grant_id],
                "non_claims": [
                    "Approval is fixture-scoped.",
                    "No production mutation is authorized."
                ]
            }
        ],
        "regression_fixtures": [
            {
                "fixture_id": regression_fixture_id,
                "fixture_status": "candidate",
                "derived_from": event_id,
                "summary": "Preserve a Workroom fixture that permits runtime_observed only with verified SVF receipt evidence.",
                "target_validation_plan_ref": plan_ref,
                "non_claims": [
                    "Fixture is not a live execution record.",
                    "Fixture does not replace Sociosphere receipt verification."
                ]
            }
        ],
        "issued_at": "2026-05-31T18:47:00Z",
        "non_claims": [
            "This fixture models receipt consumption only.",
            "This fixture does not execute SVF Actions.",
            "This fixture does not create or sign receipts."
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a DevSecOps Workroom record from validate_change v2 fixtures.")
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--observed", type=Path, default=DEFAULT_OBSERVED)
    parser.add_argument("--link", type=Path, default=DEFAULT_LINK)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    record = build_workroom(load(args.request), load(args.observed), load(args.link))
    payload = json.dumps(record, indent=2, sort_keys=False) + "\n"
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
