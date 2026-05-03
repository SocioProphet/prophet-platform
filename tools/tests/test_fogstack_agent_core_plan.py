from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = Path("schemas/agent/fogstack-agent-core-plan-v0.1.schema.json")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def build_plan(output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_agent_core_plan.py",
            "--bundle-id",
            "fogstack.access",
            "--version",
            "0.1.0",
            "--agent-id",
            "agent:fogstack.access.operator",
            "--human-anchor-role",
            "operator",
            "--runtime-mode",
            "local",
            "--isolation",
            "process",
            "--identity-mode",
            "local-dev",
            "--max-runtime-seconds",
            "900",
            "--output",
            str(output),
        ],
        check=True,
    )


def check_plan(plan: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "tools/check_fogstack_agent_core_plan.py",
            "--plan",
            str(plan),
        ],
        check=check,
        capture_output=True,
        text=True,
    )


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_build_fogstack_agent_core_plan(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.agent-core-plan.json"
    build_plan(output)

    plan = load_json(output)
    Draft202012Validator(load_json(SCHEMA)).validate(plan)

    assert plan["kind"] == "FogStackAgentCorePlan"
    assert plan["schema_version"] == "v0.1"
    assert plan["bundle_id"] == "fogstack.access"
    assert plan["version"] == "0.1.0"

    agent_plane = plan["agent_plane"]
    assert agent_plane["runtime"] == {
        "mode": "local",
        "isolation": "process",
        "max_runtime_seconds": 900,
    }
    assert agent_plane["identity"] == {
        "agent_id": "agent:fogstack.access.operator",
        "identity_mode": "local-dev",
        "human_anchor_required": True,
        "human_anchor_role": "operator",
    }
    assert agent_plane["memory"] == {
        "short_term": "run_context",
        "long_term": "disabled-by-default",
        "retention_policy": "local-demo",
    }
    assert agent_plane["observability"] == {
        "run_record_required": True,
        "trace_required": True,
        "artifact_index_required": True,
        "approval_record_required": True,
    }
    assert agent_plane["policy"] == {
        "human_approval_required_for_deploy": True,
        "network_access_default": "deny",
        "filesystem_scope": "repo-local",
        "secrets_access": "deny",
        "dangerous_actions_require_quorum": True,
    }

    tool_names = {tool["name"] for tool in agent_plane["gateway"]["allowed_tools"]}
    assert tool_names == {
        "fogstack.verify",
        "fogstack.build_deploy_plan",
        "fogstack.check_deploy_plan",
    }

    gates = {gate["id"]: gate for gate in agent_plane["approval_gates"]}
    assert gates["deploy-plan-approval"]["required_approvals"] == 1
    assert gates["deploy-plan-approval"]["human_required"] is True
    assert gates["dangerous-action-quorum"]["required_approvals"] == 3
    assert gates["dangerous-action-quorum"]["human_required"] is True


def test_check_fogstack_agent_core_plan_passes(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.agent-core-plan.json"
    build_plan(output)

    proc = check_plan(output, check=True)
    assert "FogStack agent core plan passed." in proc.stdout


def test_check_fogstack_agent_core_plan_rejects_network_allow(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.agent-core-plan.json"
    build_plan(output)

    plan = load_json(output)
    plan["agent_plane"]["policy"]["network_access_default"] = "allow"
    write_json(output, plan)

    proc = check_plan(output)
    assert proc.returncode != 0
    assert "network_access_default" in proc.stderr or "network access" in proc.stderr


def test_check_fogstack_agent_core_plan_rejects_missing_human_anchor(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.agent-core-plan.json"
    build_plan(output)

    plan = load_json(output)
    plan["agent_plane"]["identity"]["human_anchor_required"] = False
    write_json(output, plan)

    proc = check_plan(output)
    assert proc.returncode != 0
    assert "human_anchor_required" in proc.stderr or "human anchor" in proc.stderr


def test_check_fogstack_agent_core_plan_rejects_missing_required_tool(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.agent-core-plan.json"
    build_plan(output)

    plan = load_json(output)
    plan["agent_plane"]["gateway"]["allowed_tools"] = [
        tool
        for tool in plan["agent_plane"]["gateway"]["allowed_tools"]
        if tool["name"] != "fogstack.check_deploy_plan"
    ]
    write_json(output, plan)

    proc = check_plan(output)
    assert proc.returncode != 0
    assert "required allowed tool missing: fogstack.check_deploy_plan" in proc.stderr


def test_check_fogstack_agent_core_plan_rejects_weak_dangerous_quorum(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.agent-core-plan.json"
    build_plan(output)

    plan = load_json(output)
    for gate in plan["agent_plane"]["approval_gates"]:
        if gate["id"] == "dangerous-action-quorum":
            gate["required_approvals"] = 1
    write_json(output, plan)

    proc = check_plan(output)
    assert proc.returncode != 0
    assert "dangerous-action-quorum gate must require at least three human approvals" in proc.stderr
