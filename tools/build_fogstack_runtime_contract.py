#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ALLOWED_TOOLS = [
    {"name": "fogstack.verify", "purpose": "Verify FogStack bundle conformance.", "side_effects": False},
    {"name": "fogstack.build_deploy_plan", "purpose": "Build a FogStack deploy plan.", "side_effects": True},
    {"name": "fogstack.check_deploy_plan", "purpose": "Check a FogStack deploy plan.", "side_effects": False},
]


def build_contract(
    bundle_id: str,
    version: str,
    actor_id: str,
    human_anchor_role: str,
    runtime_mode: str,
    isolation: str,
    identity_mode: str,
    max_runtime_seconds: int,
) -> dict[str, Any]:
    return {
        "kind": "FogStackAgentCorpsPlan",
        "schema_version": "v0.1",
        "bundle_id": bundle_id,
        "version": version,
        "agent_corps": {
            "runtime": {
                "mode": runtime_mode,
                "isolation": isolation,
                "max_runtime_seconds": max_runtime_seconds,
            },
            "identity": {
                "agent_id": actor_id,
                "identity_mode": identity_mode,
                "human_anchor_required": True,
                "human_anchor_role": human_anchor_role,
            },
            "gateway": {
                "tool_protocols": ["mcp", "cli"],
                "allowed_tools": DEFAULT_ALLOWED_TOOLS,
            },
            "memory": {
                "short_term": "run_context",
                "long_term": "disabled-by-default",
                "retention_policy": "local-demo",
            },
            "observability": {
                "run_record_required": True,
                "trace_required": True,
                "artifact_index_required": True,
                "approval_record_required": True,
            },
            "policy": {
                "human_approval_required_for_deploy": True,
                "network_access_default": "deny",
                "filesystem_scope": "repo-local",
                "secrets_access": "deny",
                "dangerous_actions_require_quorum": True,
            },
            "approval_gates": [
                {"id": "deploy-plan-approval", "action": "approve deploy plan", "required_approvals": 1, "human_required": True},
                {"id": "dangerous-action-quorum", "action": "approve sensitive runtime action", "required_approvals": 3, "human_required": True},
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a FogStack runtime contract")
    parser.add_argument("--bundle-id", default="fogstack.access")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--actor-id", default="agent:fogstack.access.operator")
    parser.add_argument("--human-anchor-role", default="operator")
    parser.add_argument("--runtime-mode", choices=["local", "sandbox", "cluster"], default="local")
    parser.add_argument("--isolation", choices=["process", "container", "kata", "gvisor"], default="process")
    parser.add_argument("--identity-mode", choices=["local-dev", "workload", "spiffe", "oidc"], default="local-dev")
    parser.add_argument("--max-runtime-seconds", type=int, default=900)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    contract = build_contract(
        bundle_id=args.bundle_id,
        version=args.version,
        actor_id=args.actor_id,
        human_anchor_role=args.human_anchor_role,
        runtime_mode=args.runtime_mode,
        isolation=args.isolation,
        identity_mode=args.identity_mode,
        max_runtime_seconds=args.max_runtime_seconds,
    )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(contract, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
