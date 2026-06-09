#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "prophet-mesh" / "demo" / "prophet-mesh-runtime-readiness.v0.json"

REQUIRED_CONTROLS = {
    "identity",
    "policy",
    "evidence",
    "attestation",
    "revocation",
    "audit",
    "tenant_isolation",
}

REQUIRED_BLOCKS = {
    "production_ready",
    "external_action_allowed",
    "live_provider_call",
    "provider_secret_use",
    "provider_secret_display",
    "external_message_send",
    "unapproved_memory_writeback",
    "tenant_crossing",
    "customer_facing_claim",
}

REQUIRED_SOURCES = {
    "SocioProphet/prophet-mesh:specs/model-router-interface.yaml",
    "SocioProphet/prophet-mesh:examples/router-decision.accepted.json",
    "SocioProphet/prophet-mesh:examples/choir-execution-plan.accepted.json",
}


def main() -> int:
    try:
        record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERR: failed to load Prophet Mesh demo readiness fixture: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []

    if record.get("schema_version") != "0.1.0":
        errors.append("schema_version must be 0.1.0")
    if record.get("readiness_state") != "ready_for_nonprod_eval":
        errors.append("readiness_state must be ready_for_nonprod_eval")

    for key in (
        "production_ready",
        "external_action_allowed",
        "live_provider_call",
        "provider_secrets_required",
        "real_user_data_processing",
        "customer_facing_claim",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")

    if record.get("requires_human_approval") is not True:
        errors.append("requires_human_approval must be true")

    source_ids = {item.get("source_id") for item in record.get("source_basis", [])}
    missing_sources = sorted(REQUIRED_SOURCES - source_ids)
    if missing_sources:
        errors.append(f"missing source basis entries: {missing_sources}")

    upstream_repos = {item.get("repo") for item in record.get("upstream_artifacts", [])}
    if "SocioProphet/prophet-mesh" not in upstream_repos:
        errors.append("missing SocioProphet/prophet-mesh upstream artifact")

    runtime_path = record.get("runtime_path", {})
    for key in (
        "conductor_id",
        "request_id",
        "task",
        "domain",
        "intent",
        "memory_scope",
        "selected_route",
        "route_type",
        "fallback_route",
        "policy_decision",
        "approval_boundary",
    ):
        if not runtime_path.get(key):
            errors.append(f"runtime_path.{key} must be non-empty")

    if runtime_path.get("conductor_id") != "michael-agent":
        errors.append("runtime_path.conductor_id must be michael-agent")
    if runtime_path.get("policy_decision") != "requires_approval":
        errors.append("runtime_path.policy_decision must be requires_approval")
    if runtime_path.get("conductor_response_status") != "awaiting_approval":
        errors.append("runtime_path.conductor_response_status must be awaiting_approval")
    if runtime_path.get("execution_trace_status") != "awaiting_approval":
        errors.append("runtime_path.execution_trace_status must be awaiting_approval")

    specialist_agents = set(runtime_path.get("specialist_agents", []))
    for agent in ("writing-agent", "governance-sentinel"):
        if agent not in specialist_agents:
            errors.append(f"missing specialist agent: {agent}")

    evidence_refs = runtime_path.get("evidence_refs", [])
    audit_refs = runtime_path.get("audit_refs", [])
    if not evidence_refs:
        errors.append("runtime_path.evidence_refs must be non-empty")
    if not audit_refs:
        errors.append("runtime_path.audit_refs must be non-empty")

    controls = runtime_path.get("controls", {})
    for control in sorted(REQUIRED_CONTROLS):
        if controls.get(control) is not True:
            errors.append(f"runtime_path.controls.{control} must be true")

    demo_surface = record.get("demo_surface", {})
    if demo_surface.get("fixture_ready") is not True:
        errors.append("demo_surface.fixture_ready must be true")
    if demo_surface.get("ui_ready") is not True:
        errors.append("demo_surface.ui_ready must be true")
    if demo_surface.get("api_ready") is not False:
        errors.append("demo_surface.api_ready must be false")

    blocked = set(record.get("blocked_actions", []))
    missing_blocks = sorted(REQUIRED_BLOCKS - blocked)
    if missing_blocks:
        errors.append(f"missing blocked actions: {missing_blocks}")

    text = FIXTURE.read_text(encoding="utf-8")
    forbidden_tokens = ["sk-", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "BEGIN PRIVATE KEY"]
    for token in forbidden_tokens:
        if token in text:
            errors.append(f"fixture must not contain secret marker: {token}")

    if errors:
        print("ERR: Prophet Mesh demo readiness validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    print("Prophet Mesh demo readiness validates for nonprod eval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
