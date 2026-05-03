#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "agent" / "fogstack-agent-corps-plan-v0.1.schema.json"
REQUIRED_TOOLS = {
    "fogstack.verify",
    "fogstack.build_deploy_plan",
    "fogstack.check_deploy_plan",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def schema_errors(data: dict[str, Any], schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    return [
        f"schema error at {'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]


def validate_contract(path: Path, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    errors: list[str] = []
    contract = load_json(path)
    errors.extend(schema_errors(contract, schema_path))
    if errors:
        return errors

    corps = contract["agent_corps"]
    identity = corps["identity"]
    policy = corps["policy"]
    gateway = corps["gateway"]
    memory = corps["memory"]
    observability = corps["observability"]
    gates = corps["approval_gates"]

    if identity["human_anchor_required"] is not True:
        errors.append("human anchor must be required")
    if policy["network_access_default"] != "deny":
        errors.append("network access must default to deny")
    if policy["secrets_access"] != "deny":
        errors.append("secrets access must default to deny")
    if policy["filesystem_scope"] != "repo-local":
        errors.append("filesystem scope must be repo-local")
    if policy["human_approval_required_for_deploy"] is not True:
        errors.append("deploy requires human approval")
    if policy["dangerous_actions_require_quorum"] is not True:
        errors.append("sensitive actions require quorum")
    if memory["long_term"] != "disabled-by-default":
        errors.append("long term memory must be disabled by default")
    if observability["run_record_required"] is not True:
        errors.append("run record must be required")
    if observability["artifact_index_required"] is not True:
        errors.append("artifact index must be required")
    if observability["approval_record_required"] is not True:
        errors.append("approval record must be required")

    tools = gateway["allowed_tools"]
    tool_names = [tool["name"] for tool in tools]
    for tool_name in sorted({name for name in tool_names if tool_names.count(name) > 1}):
        errors.append(f"duplicate allowed tool: {tool_name}")
    for tool_name in sorted(REQUIRED_TOOLS - set(tool_names)):
        errors.append(f"required allowed tool missing: {tool_name}")

    tool_by_name = {tool["name"]: tool for tool in tools}
    if tool_by_name.get("fogstack.verify", {}).get("side_effects") is not False:
        errors.append("fogstack.verify must be side-effect free")
    if tool_by_name.get("fogstack.check_deploy_plan", {}).get("side_effects") is not False:
        errors.append("fogstack.check_deploy_plan must be side-effect free")

    gates_by_id = {gate["id"]: gate for gate in gates}
    deploy_gate = gates_by_id.get("deploy-plan-approval")
    if deploy_gate is None:
        errors.append("deploy-plan-approval gate is required")
    elif deploy_gate["human_required"] is not True or deploy_gate["required_approvals"] < 1:
        errors.append("deploy-plan-approval gate must require a human approval")

    quorum_gate = gates_by_id.get("dangerous-action-quorum")
    if quorum_gate is None:
        errors.append("quorum gate is required")
    elif quorum_gate["human_required"] is not True or quorum_gate["required_approvals"] < 3:
        errors.append("quorum gate must require at least three human approvals")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a FogStack runtime contract")
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, type=Path)
    args = parser.parse_args()

    errors = validate_contract(args.contract, args.schema)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("FogStack runtime contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
