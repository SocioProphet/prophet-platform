#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_deploy_demo(output_dir: Path, image: str, port: int) -> dict[str, Any]:
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    runtime_contract = output_dir / "fogstack.access.runtime-contract.json"
    deploy_plan = output_dir / "fogstack.access.deploy-plan.json"
    manifest_dir = output_dir / "kubernetes"
    gitops_dir = output_dir / "gitops"
    check_record = output_dir / "fogstack.access.kubernetes-manifest-check.record.json"
    readiness_record = output_dir / "fogstack.access.cluster-readiness.record.json"
    summary_path = output_dir / "fogstack.access.deploy-demo.summary.json"

    run([
        sys.executable,
        "tools/build_fogstack_runtime_contract.py",
        "--bundle-id", "fogstack.access",
        "--version", "0.1.0",
        "--actor-id", "agent:fogstack.access.operator",
        "--human-anchor-role", "operator",
        "--runtime-mode", "local",
        "--isolation", "process",
        "--identity-mode", "local-dev",
        "--max-runtime-seconds", "900",
        "--output", str(runtime_contract),
    ])
    run([
        sys.executable,
        "tools/check_fogstack_runtime_contract.py",
        "--contract", str(runtime_contract),
    ])
    run([
        sys.executable,
        "tools/build_fogstack_deploy_plan.py",
        "--manifest", "releases/manifests/fogstack.access-v0.1.manifest.json",
        "--profile", "local-dev",
        "--target", "kubernetes",
        "--namespace", "fogstack-access",
        "--health-endpoint", "/healthz",
        "--runtime-contract", str(runtime_contract),
        "--output", str(deploy_plan),
    ])
    run([
        sys.executable,
        "tools/check_fogstack_deploy_plan.py",
        "--plan", str(deploy_plan),
    ])
    run([
        sys.executable,
        "tools/render_fogstack_kubernetes_manifests.py",
        "--deploy-plan", str(deploy_plan),
        "--output-dir", str(manifest_dir),
        "--image", image,
        "--port", str(port),
    ])
    check = run([
        sys.executable,
        "tools/check_fogstack_kubernetes_manifests.py",
        "--deploy-plan", str(deploy_plan),
        "--manifest-dir", str(manifest_dir),
        "--kubectl-dry-run",
        "--record-output", str(readiness_record),
    ])
    run([
        sys.executable,
        "tools/build_fogstack_gitops_bundle.py",
        "--deploy-plan", str(deploy_plan),
        "--manifest-dir", str(manifest_dir),
        "--output-dir", str(gitops_dir),
        "--repo-url", "https://github.com/SocioProphet/prophet-platform.git",
        "--target-revision", "main",
        "--gitops-path", "gitops/fogstack.access",
    ])
    run([
        sys.executable,
        "tools/check_fogstack_gitops_bundle.py",
        "--bundle", str(gitops_dir / "gitops-bundle.json"),
    ])

    manifests = [
        manifest_dir / "configmap.yaml",
        manifest_dir / "deployment.yaml",
        manifest_dir / "service.yaml",
    ]
    readiness = json.loads(readiness_record.read_text(encoding="utf-8"))
    record = {
        "kind": "FogStackKubernetesManifestCheckRecord",
        "schema_version": "v0.1",
        "status": "passed",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "deploy_plan_ref": rel(deploy_plan),
        "agent_corps_plan_ref": rel(runtime_contract),
        "manifest_dir": rel(manifest_dir),
        "manifests": [rel(path) for path in manifests],
        "cluster_readiness_record_ref": rel(readiness_record),
        "cluster_readiness_status": readiness.get("status"),
        "cluster_validation_path": readiness.get("validation_path"),
        "checker_stdout": check.stdout.strip(),
    }
    write_json(check_record, record)

    summary = {
        "kind": "FogStackLocalDemoDeployPlanRun",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "target": "kubernetes",
        "artifacts": {
            "agent_corps_plan": rel(runtime_contract),
            "deploy_plan": rel(deploy_plan),
            "kubernetes_configmap": rel(manifest_dir / "configmap.yaml"),
            "kubernetes_deployment": rel(manifest_dir / "deployment.yaml"),
            "kubernetes_service": rel(manifest_dir / "service.yaml"),
            "kubernetes_manifest_check_record": rel(check_record),
            "cluster_readiness_record": rel(readiness_record),
            "gitops_bundle": rel(gitops_dir / "gitops-bundle.json"),
            "gitops_application": rel(gitops_dir / "application.yaml"),
            "gitops_kustomization": rel(gitops_dir / "kustomization.yaml"),
            "gitops_configmap": rel(gitops_dir / "manifests" / "configmap.yaml"),
            "gitops_deployment": rel(gitops_dir / "manifests" / "deployment.yaml"),
            "gitops_service": rel(gitops_dir / "manifests" / "service.yaml"),
            "summary": rel(summary_path),
        },
        "checks": [
            "agent_corps_plan_built",
            "agent_corps_plan_checked",
            "deploy_plan_built",
            "deploy_plan_checked",
            "kubernetes_manifests_rendered",
            "kubernetes_manifests_checked",
            "cluster_readiness_record_emitted",
            "gitops_bundle_built",
            "gitops_bundle_checked",
        ],
    }
    write_json(summary_path, summary)
    return summary


def render_summary(summary: dict[str, Any]) -> str:
    artifacts = summary["artifacts"]
    lines = [
        "FogStack local demo deploy plan passed.",
        f"Bundle: {summary['bundle_id']}@{summary['version']}",
        f"Target: {summary['target']}",
        f"Agent Corps plan: {artifacts['agent_corps_plan']}",
        f"Deploy plan: {artifacts['deploy_plan']}",
        f"Kubernetes ConfigMap: {artifacts['kubernetes_configmap']}",
        f"Kubernetes Deployment: {artifacts['kubernetes_deployment']}",
        f"Kubernetes Service: {artifacts['kubernetes_service']}",
        f"Manifest check record: {artifacts['kubernetes_manifest_check_record']}",
        f"Cluster readiness record: {artifacts['cluster_readiness_record']}",
        f"GitOps bundle: {artifacts['gitops_bundle']}",
        f"GitOps application: {artifacts['gitops_application']}",
        f"Checks passed: {len(summary['checks'])}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate FogStack local demo deploy-plan artifacts")
    parser.add_argument("--output-dir", type=Path, default=Path("build/fogstack-local-demo/deploy"))
    parser.add_argument("--image", default="ghcr.io/socioprophet/fogstack-access:0.1.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    summary = build_deploy_demo(args.output_dir, args.image, args.port)
    if args.summary:
        print(render_summary(summary), end="")
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
