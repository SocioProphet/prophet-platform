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
    "agent_corps_plan": "deploy_agent_corps_plan",
    "deploy_plan": "deploy_plan",
    "kubernetes_configmap": "deploy_kubernetes_configmap",
    "kubernetes_deployment": "deploy_kubernetes_deployment",
    "kubernetes_service": "deploy_kubernetes_service",
    "kubernetes_manifest_check_record": "deploy_kubernetes_manifest_check_record",
    "summary": "deploy_summary",
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


def append_markdown(markdown_path: Path, deploy_summary: dict[str, Any]) -> None:
    artifacts = deploy_summary["artifacts"]
    section = [
        "",
        "## Deploy plan artifacts",
        "",
        f"- Agent Corps plan: `{artifacts['agent_corps_plan']}`",
        f"- Deploy plan: `{artifacts['deploy_plan']}`",
        f"- Kubernetes ConfigMap: `{artifacts['kubernetes_configmap']}`",
        f"- Kubernetes Deployment: `{artifacts['kubernetes_deployment']}`",
        f"- Kubernetes Service: `{artifacts['kubernetes_service']}`",
        f"- Manifest check record: `{artifacts['kubernetes_manifest_check_record']}`",
        "",
    ]
    markdown_path.write_text(markdown_path.read_text(encoding="utf-8") + "\n".join(section), encoding="utf-8")


def append_html(html_path: Path, deploy_summary: dict[str, Any]) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    artifacts = deploy_summary["artifacts"]
    section = """
    <h2>Deploy plan artifacts</h2>
    <ul>
      <li><strong>Agent Corps plan:</strong> <code>{agent}</code></li>
      <li><strong>Deploy plan:</strong> <code>{plan}</code></li>
      <li><strong>Kubernetes ConfigMap:</strong> <code>{configmap}</code></li>
      <li><strong>Kubernetes Deployment:</strong> <code>{deployment}</code></li>
      <li><strong>Kubernetes Service:</strong> <code>{service}</code></li>
      <li><strong>Manifest check record:</strong> <code>{check}</code></li>
    </ul>
""".format(
        agent=esc(artifacts["agent_corps_plan"]),
        plan=esc(artifacts["deploy_plan"]),
        configmap=esc(artifacts["kubernetes_configmap"]),
        deployment=esc(artifacts["kubernetes_deployment"]),
        service=esc(artifacts["kubernetes_service"]),
        check=esc(artifacts["kubernetes_manifest_check_record"]),
    )
    html_text = html_path.read_text(encoding="utf-8")
    html_path.write_text(html_text.replace("\n  </main>", section + "\n  </main>"), encoding="utf-8")


def update_summary(summary_path: Path, deploy_summary_path: Path) -> dict[str, Any]:
    summary = load_json(summary_path)
    deploy_summary = load_json(deploy_summary_path)

    artifacts = summary.setdefault("artifacts", {})
    for source_key, target_key in DEPLOY_ARTIFACT_KEYS.items():
        artifacts[target_key] = deploy_summary["artifacts"][source_key]

    checks = summary.setdefault("checks", [])
    for check in ["deploy_plan_built", "kubernetes_manifests_rendered", "kubernetes_manifests_checked"]:
        if check not in checks:
            checks.append(check)

    write_json(summary_path, summary)
    markdown_path = path_from_ref(artifacts["summary_markdown"])
    html_path = path_from_ref(artifacts["summary_html"])
    append_markdown(markdown_path, deploy_summary)
    append_html(html_path, deploy_summary)

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
