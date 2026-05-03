#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_ARTIFACT_KEYS = {
    "node_profile": "deploy_node_profile",
    "agent_corps_plan": "deploy_agent_corps_plan",
    "deploy_plan": "deploy_plan",
    "kubernetes_configmap": "deploy_kubernetes_configmap",
    "kubernetes_deployment": "deploy_kubernetes_deployment",
    "kubernetes_service": "deploy_kubernetes_service",
    "kubernetes_manifest_check_record": "deploy_kubernetes_manifest_check_record",
    "cluster_readiness_record": "deploy_cluster_readiness_record",
    "gitops_bundle": "deploy_gitops_bundle",
    "gitops_application": "deploy_gitops_application",
    "gitops_kustomization": "deploy_gitops_kustomization",
    "gitops_configmap": "deploy_gitops_configmap",
    "gitops_deployment": "deploy_gitops_deployment",
    "gitops_service": "deploy_gitops_service",
    "summary": "deploy_summary",
}
DEPLOY_ARTIFACT_LABELS = {
    "deploy_node_profile": "Agent Machine node profile",
    "deploy_agent_corps_plan": "Agent Corps plan",
    "deploy_plan": "Deploy plan",
    "deploy_kubernetes_configmap": "Kubernetes ConfigMap",
    "deploy_kubernetes_deployment": "Kubernetes Deployment",
    "deploy_kubernetes_service": "Kubernetes Service",
    "deploy_kubernetes_manifest_check_record": "Manifest check record",
    "deploy_cluster_readiness_record": "Cluster readiness record",
    "deploy_gitops_bundle": "GitOps bundle",
    "deploy_gitops_application": "GitOps Application",
    "deploy_gitops_kustomization": "GitOps Kustomization",
    "deploy_gitops_configmap": "GitOps ConfigMap",
    "deploy_gitops_deployment": "GitOps Deployment",
    "deploy_gitops_service": "GitOps Service",
    "deploy_summary": "Deploy summary",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def path_from_ref(ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else ROOT / path


def deploy_readiness_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = summary.get("artifacts") or {}
    rows: list[dict[str, Any]] = []
    for artifact_id in DEPLOY_ARTIFACT_LABELS:
        ref = artifacts.get(artifact_id)
        if not isinstance(ref, str):
            raise SystemExit(f"ERR: deploy artifact ref missing from summary: {artifact_id}")
        path = path_from_ref(ref)
        if not path.exists() or not path.is_file():
            raise SystemExit(f"ERR: deploy artifact is missing or not a file: {ref}")
        rows.append({
            "id": artifact_id,
            "label": DEPLOY_ARTIFACT_LABELS[artifact_id],
            "ref": ref,
            "digest": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "status": "indexed",
        })
    return rows


def build_artifact_index(summary: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for artifact_id, artifact_ref in sorted((summary.get("artifacts") or {}).items()):
        if artifact_id == "artifact_index" or not isinstance(artifact_ref, str):
            continue
        if artifact_ref in seen_refs:
            continue
        seen_refs.add(artifact_ref)
        path = path_from_ref(artifact_ref)
        if not path.exists() or not path.is_file():
            raise SystemExit(f"ERR: indexed artifact is missing or not a file: {artifact_ref}")
        entries.append({
            "id": artifact_id,
            "ref": artifact_ref,
            "digest": sha256_file(path),
            "size_bytes": path.stat().st_size,
        })

    for release in summary.get("releases") or []:
        if not isinstance(release, dict):
            continue
        bundle_id = release.get("bundle_id", "unknown")
        for key in ["verify_json", "validation_record", "filesystem_release_pointer"]:
            artifact_ref = release.get(key)
            if not isinstance(artifact_ref, str) or artifact_ref in seen_refs:
                continue
            seen_refs.add(artifact_ref)
            path = path_from_ref(artifact_ref)
            if not path.exists() or not path.is_file():
                raise SystemExit(f"ERR: release artifact is missing or not a file: {artifact_ref}")
            entries.append({
                "id": f"release:{bundle_id}:{key}",
                "ref": artifact_ref,
                "digest": sha256_file(path),
                "size_bytes": path.stat().st_size,
            })

    return {
        "kind": "FogStackLocalDemoArtifactIndex",
        "schema_version": "v0.1",
        "demo_kind": summary.get("kind"),
        "pack": summary.get("pack"),
        "registry_uri": summary.get("registry_uri"),
        "release_count": len(summary.get("releases", [])),
        "artifacts": entries,
    }


def append_markdown(markdown_path: Path, readiness_rows: list[dict[str, Any]]) -> None:
    table_rows = [
        f"| `{row['id']}` | {row['label']} | `{row['ref']}` | `{row['digest']}` | `{row['status']}` |"
        for row in readiness_rows
    ]
    section = [
        "",
        "## Deploy readiness",
        "",
        "| Artifact ID | Artifact | Ref | SHA-256 digest | Status |",
        "|---|---|---|---|---|",
        *table_rows,
        "",
    ]
    markdown_path.write_text(markdown_path.read_text(encoding="utf-8") + "\n".join(section), encoding="utf-8")


def append_html(html_path: Path, readiness_rows: list[dict[str, Any]]) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    rows = "\n".join(
        "<tr>"
        f"<td><code>{esc(row['id'])}</code></td>"
        f"<td>{esc(row['label'])}</td>"
        f"<td><code>{esc(row['ref'])}</code></td>"
        f"<td><code>{esc(row['digest'])}</code></td>"
        f"<td>{esc(row['status'])}</td>"
        "</tr>"
        for row in readiness_rows
    )
    section = f"""
    <h2>Deploy readiness</h2>
    <table>
      <thead><tr><th>Artifact ID</th><th>Artifact</th><th>Ref</th><th>SHA-256 digest</th><th>Status</th></tr></thead>
      <tbody>
        {rows}
      </tbody>
    </table>
"""
    html_text = html_path.read_text(encoding="utf-8")
    html_path.write_text(html_text.replace("\n  </main>", section + "\n  </main>"), encoding="utf-8")


def update_summary(summary_path: Path, deploy_summary_path: Path) -> dict[str, Any]:
    summary = load_json(summary_path)
    deploy_summary = load_json(deploy_summary_path)

    artifacts = summary.setdefault("artifacts", {})
    for source_key, target_key in DEPLOY_ARTIFACT_KEYS.items():
        artifacts[target_key] = deploy_summary["artifacts"][source_key]

    checks = summary.setdefault("checks", [])
    for check in ["node_profile_built", "deploy_plan_built", "kubernetes_manifests_rendered", "kubernetes_manifests_checked", "cluster_readiness_record_emitted", "gitops_bundle_built", "gitops_bundle_checked"]:
        if check not in checks:
            checks.append(check)

    readiness_rows = deploy_readiness_rows(summary)
    write_json(summary_path, summary)
    markdown_path = path_from_ref(artifacts["summary_markdown"])
    html_path = path_from_ref(artifacts["summary_html"])
    append_markdown(markdown_path, readiness_rows)
    append_html(html_path, readiness_rows)

    artifact_index_path = path_from_ref(artifacts["artifact_index"])
    write_json(artifact_index_path, build_artifact_index(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge local demo deploy-plan artifacts into the local demo summaries and digest index")
    parser.add_argument("--summary-json", type=Path, default=Path("build/fogstack-local-demo/fogstack-local-demo.summary.json"))
    parser.add_argument("--deploy-summary-json", type=Path, default=Path("build/fogstack-local-demo/deploy/fogstack.access.deploy-demo.summary.json"))
    args = parser.parse_args()

    summary_path = args.summary_json if args.summary_json.is_absolute() else ROOT / args.summary_json
    deploy_summary_path = args.deploy_summary_json if args.deploy_summary_json.is_absolute() else ROOT / args.deploy_summary_json
    summary = update_summary(summary_path, deploy_summary_path)
    print(json.dumps({"kind": "FogStackLocalDemoDeployArtifactUpdate", "status": "passed", "artifact_index": summary["artifacts"]["artifact_index"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
