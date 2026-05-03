from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = Path("schemas/agent/fogstack-agent-corps-plan-v0.1.schema.json")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_contract(output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_runtime_contract.py",
            "--bundle-id",
            "fogstack.access",
            "--version",
            "0.1.0",
            "--actor-id",
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


def check_contract(path: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "tools/check_fogstack_runtime_contract.py",
            "--contract",
            str(path),
        ],
        check=check,
        capture_output=True,
        text=True,
    )


def test_build_fogstack_runtime_contract(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.runtime-contract.json"
    build_contract(output)

    contract = load_json(output)
    Draft202012Validator(load_json(SCHEMA)).validate(contract)

    assert contract["kind"] == "FogStackAgentCorpsPlan"
    assert contract["schema_version"] == "v0.1"
    assert contract["bundle_id"] == "fogstack.access"
    assert contract["version"] == "0.1.0"

    corps = contract["agent_corps"]
    assert corps["runtime"] == {
        "mode": "local",
        "isolation": "process",
        "max_runtime_seconds": 900,
    }
    assert corps["identity"] == {
        "agent_id": "agent:fogstack.access.operator",
        "identity_mode": "local-dev",
        "human_anchor_required": True,
        "human_anchor_role": "operator",
    }
    assert corps["memory"] == {
        "short_term": "run_context",
        "long_term": "disabled-by-default",
        "retention_policy": "local-demo",
    }
    assert corps["observability"] == {
        "run_record_required": True,
        "trace_required": True,
        "artifact_index_required": True,
        "approval_record_required": True,
    }
    assert corps["policy"] == {
        "human_approval_required_for_deploy": True,
        "network_access_default": "deny",
        "filesystem_scope": "repo-local",
        "secrets_access": "deny",
        "dangerous_actions_require_quorum": True,
    }

    tool_names = {tool["name"] for tool in corps["gateway"]["allowed_tools"]}
    assert tool_names == {
        "fogstack.verify",
        "fogstack.build_deploy_plan",
        "fogstack.check_deploy_plan",
    }

    gates = {gate["id"]: gate for gate in corps["approval_gates"]}
    assert gates["deploy-plan-approval"]["required_approvals"] == 1
    assert gates["deploy-plan-approval"]["human_required"] is True
    assert gates["dangerous-action-quorum"]["required_approvals"] == 3
    assert gates["dangerous-action-quorum"]["human_required"] is True


def test_check_fogstack_runtime_contract_passes(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.runtime-contract.json"
    build_contract(output)
    proc = check_contract(output, check=True)
    assert "FogStack runtime contract passed." in proc.stdout


def test_check_fogstack_runtime_contract_rejects_network_allow(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.runtime-contract.json"
    build_contract(output)
    contract = load_json(output)
    contract["agent_corps"]["policy"]["network_access_default"] = "allow"
    write_json(output, contract)
    proc = check_contract(output)
    assert proc.returncode != 0
    assert "network_access_default" in proc.stderr or "network access" in proc.stderr


def test_check_fogstack_runtime_contract_rejects_missing_human_anchor(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.runtime-contract.json"
    build_contract(output)
    contract = load_json(output)
    contract["agent_corps"]["identity"]["human_anchor_required"] = False
    write_json(output, contract)
    proc = check_contract(output)
    assert proc.returncode != 0
    assert "human_anchor_required" in proc.stderr or "human anchor" in proc.stderr


def test_check_fogstack_runtime_contract_rejects_missing_required_tool(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.runtime-contract.json"
    build_contract(output)
    contract = load_json(output)
    contract["agent_corps"]["gateway"]["allowed_tools"] = [
        tool
        for tool in contract["agent_corps"]["gateway"]["allowed_tools"]
        if tool["name"] != "fogstack.check_deploy_plan"
    ]
    write_json(output, contract)
    proc = check_contract(output)
    assert proc.returncode != 0
    assert "required allowed tool missing: fogstack.check_deploy_plan" in proc.stderr


def test_check_fogstack_runtime_contract_rejects_weak_quorum(tmp_path: Path) -> None:
    output = tmp_path / "fogstack.access.runtime-contract.json"
    build_contract(output)
    contract = load_json(output)
    for gate in contract["agent_corps"]["approval_gates"]:
        if gate["id"] == "dangerous-action-quorum":
            gate["required_approvals"] = 1
    write_json(output, contract)
    proc = check_contract(output)
    assert proc.returncode != 0
    assert "quorum gate must require at least three human approvals" in proc.stderr
