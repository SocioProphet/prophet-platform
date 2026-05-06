#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        "sociosphere_record_ref": "github://SocioProphet/sociosphere/registry/state-coherence/fogstack-local-demo-state-coherence-v0.1.json",
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


def render_state_coherence_markdown(state_coherence: dict[str, Any]) -> str:
    repo_rows = [
        f"| `{entry['id']}` | `{entry['repo_ref']}` | `{entry['demo_binding']}` | {entry['role']} |"
        for entry in state_coherence["repo_refs"]
    ]
    surface_rows = [f"- `{surface}`" for surface in state_coherence["integration_surfaces"]]
    principle_rows = [f"- {principle}" for principle in state_coherence["required_demo_principles"]]
    return "\n".join([
        "# FogStack State Coherence",
        "",
        f"Status: **{state_coherence['status']}**",
        f"Posture: `{state_coherence['posture']}`",
        f"Production boundary: {state_coherence['production_boundary']}",
        f"Sociosphere record: `{state_coherence['sociosphere_record_ref']}`",
        "",
        "## Repo bindings",
        "",
        "| ID | Repo | Demo binding | Role |",
        "|---|---|---|---|",
        *repo_rows,
        "",
        "## Integration surfaces",
        "",
        *surface_rows,
        "",
        "## Required demo principles",
        "",
        *principle_rows,
        "",
    ])


def render_state_coherence_html(state_coherence: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    repo_rows = "\n".join(
        "<tr>"
        f"<td><code>{esc(entry['id'])}</code></td>"
        f"<td><code>{esc(entry['repo_ref'])}</code></td>"
        f"<td><code>{esc(entry['demo_binding'])}</code></td>"
        f"<td>{esc(entry['role'])}</td>"
        "</tr>"
        for entry in state_coherence["repo_refs"]
    )
    surface_items = "\n".join(
        f"<li><code>{esc(surface)}</code></li>" for surface in state_coherence["integration_surfaces"]
    )
    principle_items = "\n".join(
        f"<li>{esc(principle)}</li>" for principle in state_coherence["required_demo_principles"]
    )
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>FogStack State Coherence</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; line-height: 1.5; }}
    main {{ max-width: 1120px; }}
    .status {{ display: inline-block; padding: 0.25rem 0.6rem; border: 1px solid currentColor; border-radius: 999px; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid currentColor; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
    code {{ word-break: break-word; }}
  </style>
</head>
<body>
  <main>
    <h1>FogStack State Coherence</h1>
    <p class=\"status\">Status: {esc(state_coherence['status'])}</p>
    <dl>
      <dt>Posture</dt><dd><code>{esc(state_coherence['posture'])}</code></dd>
      <dt>Production boundary</dt><dd>{esc(state_coherence['production_boundary'])}</dd>
      <dt>Sociosphere record</dt><dd><code>{esc(state_coherence['sociosphere_record_ref'])}</code></dd>
    </dl>

    <h2>Repo bindings</h2>
    <table>
      <thead><tr><th>ID</th><th>Repo</th><th>Demo binding</th><th>Role</th></tr></thead>
      <tbody>{repo_rows}</tbody>
    </table>

    <h2>Integration surfaces</h2>
    <ul>{surface_items}</ul>

    <h2>Required demo principles</h2>
    <ul>{principle_items}</ul>
  </main>
</body>
</html>
"""


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
    state_coherence_markdown_path = output_dir / "fogstack-local-demo.state-coherence.md"
    state_coherence_html_path = output_dir / "state-coherence.html"

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
    write_text(state_coherence_markdown_path, render_state_coherence_markdown(state_coherence))
    write_text(state_coherence_html_path, render_state_coherence_html(state_coherence))

    summary = {
        "kind": "FogStackLocalDemoFullRun",
        "schema_version": "v0.1",
        "status": "passed",
        "output_dir": rel(output_dir),
        "artifacts": {
            "local_demo_summary": rel(summary_path),
            "local_demo_markdown": rel(output_dir / "fogstack-local-demo.summary.md"),
            "local_demo_html": rel(output_dir / "index.html"),
            "state_coherence_markdown": rel(state_coherence_markdown_path),
            "state_coherence_html": rel(state_coherence_html_path),
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
            "state_coherence_operator_artifacts_emitted",
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
        f"State coherence Markdown: {artifacts['state_coherence_markdown']}",
        f"State coherence HTML: {artifacts['state_coherence_html']}",
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
