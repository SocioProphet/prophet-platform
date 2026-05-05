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


STATE_COHERENCE_REPO_REFS = [
    {
        "id": "fogstack-runtime-spine",
        "repo_ref": "github://SocioProphet/prophet-platform",
        "role": "bounded local demo proof, release proof, deploy plan, GitOps, runtime dry-run, and parity readiness spine",
        "demo_binding": "primary",
    },
    {
        "id": "estate-control-plane",
        "repo_ref": "github://SocioProphet/sociosphere",
        "role": "estate intelligence, repository topology, control-plane status, and cross-repo coherence registry",
        "demo_binding": "control-plane",
    },
    {
        "id": "sourceos-state-integrity",
        "repo_ref": "github://SourceOS-Linux/sourceos-syncd",
        "role": "local-first state integrity, event/report contracts, repair planning, and store-backed evidence surface",
        "demo_binding": "supporting-evidence",
    },
    {
        "id": "agent-machine-substrate",
        "repo_ref": "github://SourceOS-Linux/agent-machine",
        "role": "Agent Machine bootstrap, trust, activation, provenance, release evidence, and governed local execution surface",
        "demo_binding": "substrate",
    },
    {
        "id": "sourceos-operator-surfaces",
        "repo_ref": "github://SourceOS-Linux/BearBrowser",
        "role": "governed browser/operator surface, policy actions, provenance events, and local app status/open/reset controls",
        "demo_binding": "operator-surface",
    },
    {
        "id": "guardrail-boundary",
        "repo_ref": "github://SocioProphet/guardrail-fabric",
        "role": "SourceOS guardrail decision ABI, hook adapter, policy simulation, deterministic baseline policies, and anti-tamper controls",
        "demo_binding": "policy-boundary",
    },
    {
        "id": "agentplane-governance-context",
        "repo_ref": "github://SocioProphet/agentplane",
        "role": "agent runtime governance context, protocol identity aliases, run/replay/session evidence propagation",
        "demo_binding": "runtime-governance",
    },
    {
        "id": "semantic-contract-plane",
        "repo_ref": "github://SocioProphet/ontogenesis",
        "role": "semantic enterprise ontology, ValueFlows/SHIR projection, sector scenarios, and OrgGov semantic alignment",
        "demo_binding": "semantic-layer",
    },
]


STATE_COHERENCE_INTEGRATION_SURFACES = [
    "release-proof-to-runtime-evidence",
    "gitops-readiness-to-local-demo-summary",
    "runtime-dry-run-to-agentplane-run-linkage",
    "runtime-dry-run-to-policyplane-decision-linkage",
    "agent-machine-node-profile-to-runtime-adapter",
    "immutable-update-readiness-to-demo-artifact-index",
    "sourceos-state-integrity-to-supporting-evidence-plane",
    "guardrail-decision-abi-to-policy-boundary",
    "operator-surfaces-to-sourceos-node-profile",
    "semantic-contracts-to-governed-evidence-plane",
]


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


def build_state_coherence_summary() -> dict[str, Any]:
    return {
        "kind": "FogStackStateCoherenceSummary",
        "schema_version": "v0.1",
        "posture": "compressed-estate-demo-coherence",
        "status": "bounded-local-demo-ready",
        "production_boundary": "non-mutating local proof; live mutation, production signing, registry publication, and managed multi-tenant service operations remain post-MVP",
        "repo_refs": STATE_COHERENCE_REPO_REFS,
        "integration_surfaces": STATE_COHERENCE_INTEGRATION_SURFACES,
        "required_demo_principles": [
            "one operator command should produce one evidence directory",
            "every generated artifact should be digest-indexed or explicitly reported as a supporting external ref",
            "live cluster mutation must remain disabled by default",
            "policy and guardrail decisions must be explicit artifacts, not implicit runtime behavior",
            "SourceOS local-first state integrity must be treated as substrate evidence, not an optional sidecar",
        ],
    }


def run_full_demo(output_dir: Path, clean: bool) -> dict[str, Any]:
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    deploy_dir = output_dir / "deploy"
    summary_path = output_dir / "fogstack-local-demo.summary.json"
    deploy_summary_path = deploy_dir / "fogstack.access.deploy-demo.summary.json"
    node_inventory_path = deploy_dir / "fogstack.access.agent-machine-node-inventory.record.json"
    immutable_update_path = deploy_dir / "fogstack.access.immutable-update-readiness.record.json"
    gitops_readiness_path = deploy_dir / "fogstack.access.gitops-readiness.record.json"
    live_preflight_path = deploy_dir / "fogstack.access.live-cluster-preflight.record.json"
    runtime_adapter_path = deploy_dir / "fogstack.access.local-cluster-runtime-adapter.json"
    runtime_dry_run_path = deploy_dir / "fogstack.access.runtime-dry-run.record.json"
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
        "tools/update_fogstack_local_demo_gitops_readiness.py",
        "--summary-json",
        str(summary_path),
        "--gitops-readiness-record",
        str(gitops_readiness_path),
    ])
    run([
        sys.executable,
        "tools/update_fogstack_local_demo_runtime_evidence.py",
        "--summary-json",
        str(summary_path),
        "--runtime-adapter",
        str(runtime_adapter_path),
        "--runtime-dry-run-record",
        str(runtime_dry_run_path),
    ])
    run([
        sys.executable,
        "tools/check_fogstack_local_demo_artifact_index.py",
        "--index",
        str(artifact_index_path),
    ])

    state_coherence = build_state_coherence_summary()
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
            "node_inventory_record": rel(node_inventory_path),
            "immutable_update_readiness_record": rel(immutable_update_path),
            "deploy_plan": rel(deploy_dir / "fogstack.access.deploy-plan.json"),
            "agent_corps_plan": rel(deploy_dir / "fogstack.access.runtime-contract.json"),
            "kubernetes_configmap": rel(deploy_dir / "kubernetes" / "configmap.yaml"),
            "kubernetes_deployment": rel(deploy_dir / "kubernetes" / "deployment.yaml"),
            "kubernetes_service": rel(deploy_dir / "kubernetes" / "service.yaml"),
            "kubernetes_manifest_check_record": rel(deploy_dir / "fogstack.access.kubernetes-manifest-check.record.json"),
            "cluster_readiness_record": rel(deploy_dir / "fogstack.access.cluster-readiness.record.json"),
            "gitops_bundle": rel(deploy_dir / "gitops" / "gitops-bundle.json"),
            "gitops_application": rel(deploy_dir / "gitops" / "application.yaml"),
            "gitops_kustomization": rel(deploy_dir / "gitops" / "kustomization.yaml"),
            "gitops_configmap": rel(deploy_dir / "gitops" / "manifests" / "configmap.yaml"),
            "gitops_deployment": rel(deploy_dir / "gitops" / "manifests" / "deployment.yaml"),
            "gitops_service": rel(deploy_dir / "gitops" / "manifests" / "service.yaml"),
            "gitops_readiness_record": rel(gitops_readiness_path),
            "live_cluster_preflight_record": rel(live_preflight_path),
            "runtime_adapter": rel(runtime_adapter_path),
            "runtime_dry_run_record": rel(runtime_dry_run_path),
        },
        "state_coherence": state_coherence,
        "checks": [
            "local_demo_generated",
            "deploy_plan_generated",
            "deploy_artifacts_integrated",
            "node_inventory_record_indexed",
            "immutable_update_readiness_record_indexed",
            "cluster_readiness_record_indexed",
            "gitops_bundle_indexed",
            "gitops_readiness_record_indexed",
            "live_cluster_preflight_record_indexed",
            "runtime_adapter_indexed",
            "runtime_dry_run_record_indexed",
            "artifact_index_checked",
            "state_coherence_surfaces_bound",
        ],
    }
    write_json(full_summary_path, summary)
    return summary


def render_summary(summary: dict[str, Any]) -> str:
    artifacts = summary["artifacts"]
    state_coherence = summary["state_coherence"]
    lines = [
        "FogStack full local demo passed.",
        f"Output directory: {summary['output_dir']}",
        f"HTML summary: {artifacts['local_demo_html']}",
        f"Artifact index: {artifacts['artifact_index']}",
        f"Agent Machine node inventory: {artifacts['node_inventory_record']}",
        f"Immutable update readiness: {artifacts['immutable_update_readiness_record']}",
        f"Deploy plan: {artifacts['deploy_plan']}",
        f"Kubernetes deployment: {artifacts['kubernetes_deployment']}",
        f"Cluster readiness record: {artifacts['cluster_readiness_record']}",
        f"GitOps bundle: {artifacts['gitops_bundle']}",
        f"GitOps application: {artifacts['gitops_application']}",
        f"GitOps readiness record: {artifacts['gitops_readiness_record']}",
        f"Live cluster preflight record: {artifacts['live_cluster_preflight_record']}",
        f"Runtime adapter: {artifacts['runtime_adapter']}",
        f"Runtime dry-run record: {artifacts['runtime_dry_run_record']}",
        f"State coherence posture: {state_coherence['posture']}",
        f"State coherence repo refs: {len(state_coherence['repo_refs'])}",
        f"State coherence integration surfaces: {len(state_coherence['integration_surfaces'])}",
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
