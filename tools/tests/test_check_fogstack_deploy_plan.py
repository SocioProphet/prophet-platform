from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")


def build_runtime_contract(output: Path, *, bundle_id: str = "fogstack.access", version: str = "0.1.0") -> None:
    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_runtime_contract.py",
            "--bundle-id",
            bundle_id,
            "--version",
            version,
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


def build_plan(output: Path, runtime_contract: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_deploy_plan.py",
            "--manifest",
            str(MANIFEST),
            "--profile",
            "local-dev",
            "--target",
            "local",
            "--namespace",
            "fogstack-access",
            "--health-endpoint",
            "/healthz",
            "--runtime-contract",
            str(runtime_contract),
            "--output",
            str(output),
        ],
        check=True,
    )


def check_plan(plan: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "tools/check_fogstack_deploy_plan.py",
            "--plan",
            str(plan),
        ],
        check=check,
        capture_output=True,
        text=True,
    )


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_check_fogstack_deploy_plan_passes(tmp_path: Path) -> None:
    contract = tmp_path / "fogstack.access.runtime-contract.json"
    plan = tmp_path / "fogstack.access.deploy-plan.json"
    build_runtime_contract(contract)
    build_plan(plan, contract)

    proc = check_plan(plan, check=True)
    assert "FogStack deploy plan passed." in proc.stdout


def test_check_fogstack_deploy_plan_rejects_missing_required_field(tmp_path: Path) -> None:
    contract = tmp_path / "fogstack.access.runtime-contract.json"
    plan = tmp_path / "fogstack.access.deploy-plan.json"
    build_runtime_contract(contract)
    build_plan(plan, contract)

    data = json.loads(plan.read_text(encoding="utf-8"))
    del data["namespace"]
    write_json(plan, data)

    proc = check_plan(plan)
    assert proc.returncode != 0
    assert "schema error" in proc.stderr
    assert "namespace" in proc.stderr


def test_check_fogstack_deploy_plan_rejects_bad_manifest_digest(tmp_path: Path) -> None:
    contract = tmp_path / "fogstack.access.runtime-contract.json"
    plan = tmp_path / "fogstack.access.deploy-plan.json"
    build_runtime_contract(contract)
    build_plan(plan, contract)

    data = json.loads(plan.read_text(encoding="utf-8"))
    data["manifest_digest"] = "sha256:" + ("0" * 64)
    data["artifacts"] = [
        artifact if artifact["id"] != "manifest" else {**artifact, "digest": data["manifest_digest"]}
        for artifact in data["artifacts"]
    ]
    write_json(plan, data)

    proc = check_plan(plan)
    assert proc.returncode != 0
    assert "manifest_digest mismatch" in proc.stderr


def test_check_fogstack_deploy_plan_rejects_tampered_runtime_contract(tmp_path: Path) -> None:
    contract = tmp_path / "fogstack.access.runtime-contract.json"
    plan = tmp_path / "fogstack.access.deploy-plan.json"
    build_runtime_contract(contract)
    build_plan(plan, contract)

    contract_data = json.loads(contract.read_text(encoding="utf-8"))
    contract_data["agent_corps"]["runtime"]["max_runtime_seconds"] = 901
    write_json(contract, contract_data)

    proc = check_plan(plan)
    assert proc.returncode != 0
    assert "agent_corps_plan_digest mismatch" in proc.stderr or "artifact[2] digest mismatch" in proc.stderr


def test_check_fogstack_deploy_plan_rejects_mismatched_runtime_contract_version(tmp_path: Path) -> None:
    contract = tmp_path / "fogstack.access.runtime-contract.json"
    plan = tmp_path / "fogstack.access.deploy-plan.json"
    build_runtime_contract(contract)
    build_plan(plan, contract)

    data = json.loads(plan.read_text(encoding="utf-8"))
    contract_data = json.loads(contract.read_text(encoding="utf-8"))
    contract_data["version"] = "9.9.9"
    write_json(contract, contract_data)
    data["agent_corps_plan_digest"] = "sha256:" + ("0" * 64)
    data["artifacts"] = [
        artifact if artifact["id"] != "agent-corps-plan" else {**artifact, "digest": data["agent_corps_plan_digest"]}
        for artifact in data["artifacts"]
    ]
    write_json(plan, data)

    proc = check_plan(plan)
    assert proc.returncode != 0
    assert "Agent Corps plan version does not match deploy plan" in proc.stderr


def test_check_fogstack_deploy_plan_rejects_tampered_artifact(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.yaml"
    manifest = tmp_path / "manifest.json"
    contract = tmp_path / "runtime-contract.json"
    plan = tmp_path / "deploy-plan.json"

    original_bundle = Path("bundles/fogstack.access-v0.1.yaml")
    original_manifest = Path("releases/manifests/fogstack.access-v0.1.manifest.json")
    bundle.write_text(original_bundle.read_text(encoding="utf-8"), encoding="utf-8")
    manifest_data = json.loads(original_manifest.read_text(encoding="utf-8"))
    manifest_data["bundle"] = str(bundle)
    manifest.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
    build_runtime_contract(contract)

    build_plan_input = subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_deploy_plan.py",
            "--manifest",
            str(manifest),
            "--profile",
            "local-dev",
            "--target",
            "local",
            "--namespace",
            "fogstack-access",
            "--runtime-contract",
            str(contract),
            "--output",
            str(plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert build_plan_input.returncode == 0

    bundle.write_text(bundle.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")

    proc = check_plan(plan)
    assert proc.returncode != 0
    assert "bundle_digest mismatch" in proc.stderr or "artifact[0] digest mismatch" in proc.stderr
