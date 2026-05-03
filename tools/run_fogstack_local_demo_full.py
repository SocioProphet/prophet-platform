#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def run_full_demo(output_dir: Path, clean: bool) -> dict[str, Any]:
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    deploy_dir = output_dir / "deploy"
    summary_path = output_dir / "fogstack-local-demo.summary.json"
    deploy_summary_path = deploy_dir / "fogstack.access.deploy-demo.summary.json"
    artifact_index_path = output_dir / "demo-artifacts.index.json"
    full_summary_path = output_dir / "fogstack-local-demo.full.summary.json"

    run([
        sys.executable,
        "tools/run_fogstack_local_demo.py",
        "--pack",
        "all",
        "--output-dir",
        str(output_dir),
        "--summary",
    ])
    run([
        sys.executable,
        "tools/run_fogstack_local_demo_deploy_plan.py",
        "--output-dir",
        str(deploy_dir),
        "--summary",
    ])
    run([
        sys.executable,
        "tools/update_fogstack_local_demo_deploy_artifacts.py",
        "--summary-json",
        str(summary_path),
        "--deploy-summary-json",
        str(deploy_summary_path),
    ])
    run([
        sys.executable,
        "tools/check_fogstack_local_demo_artifact_index.py",
        "--index",
        str(artifact_index_path),
    ])

    summary = {
        "kind": "FogStackLocalDemoFullRun",
        "schema_version": "v0.1",
        "status": "passed",
        "output_dir": rel(output_dir),
        "artifacts": {
            "local_demo_summary": rel(summary_path),
            "local_demo_markdown": rel(output_dir / "fogstack-local-demo.summary.md"),
            "local_demo_html": rel(output_dir / "index.html"),
            "artifact_index": rel(artifact_index_path),
            "deploy_summary": rel(deploy_summary_path),
            "deploy_plan": rel(deploy_dir / "fogstack.access.deploy-plan.json"),
            "agent_corps_plan": rel(deploy_dir / "fogstack.access.runtime-contract.json"),
            "kubernetes_configmap": rel(deploy_dir / "kubernetes" / "configmap.yaml"),
            "kubernetes_deployment": rel(deploy_dir / "kubernetes" / "deployment.yaml"),
            "kubernetes_service": rel(deploy_dir / "kubernetes" / "service.yaml"),
            "kubernetes_manifest_check_record": rel(deploy_dir / "fogstack.access.kubernetes-manifest-check.record.json"),
            "cluster_readiness_record": rel(deploy_dir / "fogstack.access.cluster-readiness.record.json"),
        },
        "checks": [
            "local_demo_generated",
            "deploy_plan_generated",
            "deploy_artifacts_integrated",
            "cluster_readiness_record_indexed",
            "artifact_index_checked",
        ],
    }
    write_json(full_summary_path, summary)
    return summary


def render_summary(summary: dict[str, Any]) -> str:
    artifacts = summary["artifacts"]
    lines = [
        "FogStack full local demo passed.",
        f"Output directory: {summary['output_dir']}",
        f"HTML summary: {artifacts['local_demo_html']}",
        f"Artifact index: {artifacts['artifact_index']}",
        f"Deploy plan: {artifacts['deploy_plan']}",
        f"Kubernetes deployment: {artifacts['kubernetes_deployment']}",
        f"Cluster readiness record: {artifacts['cluster_readiness_record']}",
        f"Checks passed: {len(summary['checks'])}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full FogStack local demo proof path")
    parser.add_argument("--output-dir", type=Path, default=Path("build/fogstack-local-demo"))
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    summary = run_full_demo(args.output_dir, clean=not args.no_clean)
    if args.summary:
        print(render_summary(summary), end="")
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
