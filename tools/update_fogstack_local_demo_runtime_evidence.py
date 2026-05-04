#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = {
    "deploy_runtime_adapter": "Runtime adapter",
    "deploy_runtime_dry_run_record": "Runtime dry-run record",
}
SURFACES = ["turtleterm", "bearbrowser"]


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


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def refresh_index(index_path: Path, refs_by_id: dict[str, str]) -> None:
    index = load_json(index_path)
    by_id = {entry["id"]: entry for entry in index.get("artifacts", []) if isinstance(entry, dict) and entry.get("id")}
    for artifact_id, artifact_ref in refs_by_id.items():
        by_id[artifact_id] = {"id": artifact_id, "ref": artifact_ref}

    refreshed = []
    for artifact_id in sorted(by_id):
        entry = by_id[artifact_id]
        ref = entry.get("ref")
        if not isinstance(ref, str) or not ref:
            continue
        path = path_from_ref(ref)
        if not path.exists() or not path.is_file():
            raise SystemExit(f"ERR: indexed artifact missing while refreshing: {ref}")
        refreshed.append({
            "id": artifact_id,
            "ref": ref,
            "digest": sha256_file(path),
            "size_bytes": path.stat().st_size,
        })
    index["artifacts"] = refreshed
    write_json(index_path, index)


def runtime_readiness(runtime_adapter_ref: str, runtime_dry_run_ref: str) -> dict[str, Any]:
    adapter = load_json(path_from_ref(runtime_adapter_ref))
    dry_run = load_json(path_from_ref(runtime_dry_run_ref))
    node_profile_ref = dry_run.get("node_profile_ref") or adapter.get("inputs", {}).get("node_profile_ref")
    if not isinstance(node_profile_ref, str) or not node_profile_ref:
        raise SystemExit("ERR: runtime evidence missing node profile ref")
    node_profile = load_json(path_from_ref(node_profile_ref))
    surfaces = {surface.get("id"): surface for surface in node_profile.get("use_surfaces", []) if isinstance(surface, dict)}
    missing_surfaces = [surface_id for surface_id in SURFACES if surface_id not in surfaces]
    if missing_surfaces:
        raise SystemExit(f"ERR: node profile missing required use surfaces: {', '.join(missing_surfaces)}")
    agentplane_run = dry_run.get("agentplane_run")
    if not isinstance(agentplane_run, dict):
        raise SystemExit("ERR: runtime dry-run evidence missing AgentPlane run linkage")

    return {
        "node_profile_ref": node_profile_ref,
        "node_profile_digest": dry_run.get("node_profile_digest") or adapter.get("inputs", {}).get("node_profile_digest"),
        "agentplane_run": agentplane_run,
        "surfaces": surfaces,
        "dry_run_mode": dry_run.get("dry_run_result", {}).get("mode"),
        "validation_path": dry_run.get("dry_run_result", {}).get("validation_path"),
        "mutated_cluster": dry_run.get("dry_run_result", {}).get("mutated_cluster"),
        "live_apply_allowed": dry_run.get("runtime_policy", {}).get("live_apply_allowed"),
        "requires_human_approval": dry_run.get("runtime_policy", {}).get("requires_human_approval"),
    }


def append_markdown(markdown_path: Path, refs_by_id: dict[str, str], readiness: dict[str, Any]) -> None:
    rows = []
    for artifact_id, label in ARTIFACTS.items():
        ref = refs_by_id[artifact_id]
        digest = sha256_file(path_from_ref(ref))
        rows.append(f"| `{artifact_id}` | {label} | `{ref}` | `{digest}` | `indexed` |")

    surface_rows = []
    for surface_id in SURFACES:
        surface = readiness["surfaces"][surface_id]
        surface_rows.append(
            f"| {surface['name']} | `{surface['repo_ref']}` | `{surface['surface_type']}` | "
            f"`first_class={str(surface['first_class']).lower()}; agentplane_visible={str(surface['agentplane_visible']).lower()}; policyplane_guarded={str(surface['policyplane_guarded']).lower()}` |"
        )
    agentplane = readiness["agentplane_run"]

    section = "\n".join([
        "",
        "## Runtime evidence",
        "",
        "| Artifact ID | Artifact | Ref | SHA-256 digest | Status |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "## Runtime readiness",
        "",
        "| Signal | Value |",
        "|---|---|",
        f"| AgentPlane run ID | `{agentplane['run_id']}` |",
        f"| AgentPlane run ref | `{agentplane['run_ref']}` |",
        f"| AgentPlane ref | `{agentplane['agentplane_ref']}` |",
        f"| Requested by | `{agentplane['requested_by']}` |",
        f"| AgentPlane execution mode | `{agentplane['execution_mode']}` |",
        f"| AgentPlane approval state | `{agentplane['approval_state']}` |",
        f"| Node profile | `{readiness['node_profile_ref']}` |",
        f"| Node profile digest | `{readiness['node_profile_digest']}` |",
        f"| Dry-run mode | `{readiness['dry_run_mode']}` |",
        f"| Validation path | `{readiness['validation_path']}` |",
        f"| Mutated cluster | `{str(readiness['mutated_cluster']).lower()}` |",
        f"| Live apply allowed | `{str(readiness['live_apply_allowed']).lower()}` |",
        f"| Human approval required | `{str(readiness['requires_human_approval']).lower()}` |",
        "",
        "| Use surface | Repo | Type | Governance |",
        "|---|---|---|---|",
        *surface_rows,
        "",
    ])
    markdown_path.write_text(markdown_path.read_text(encoding="utf-8") + section, encoding="utf-8")


def append_html(html_path: Path, refs_by_id: dict[str, str], readiness: dict[str, Any]) -> None:
    evidence_rows = []
    for artifact_id, label in ARTIFACTS.items():
        ref = refs_by_id[artifact_id]
        digest = sha256_file(path_from_ref(ref))
        evidence_rows.append(
            f"<tr><td><code>{html.escape(artifact_id)}</code></td>"
            f"<td>{html.escape(label)}</td>"
            f"<td><code>{html.escape(ref)}</code></td>"
            f"<td><code>{html.escape(digest)}</code></td>"
            "<td>indexed</td></tr>"
        )

    surface_rows = []
    for surface_id in SURFACES:
        surface = readiness["surfaces"][surface_id]
        governance = (
            f"first_class={str(surface['first_class']).lower()}; "
            f"agentplane_visible={str(surface['agentplane_visible']).lower()}; "
            f"policyplane_guarded={str(surface['policyplane_guarded']).lower()}"
        )
        surface_rows.append(
            f"<tr><td>{html.escape(surface['name'])}</td>"
            f"<td><code>{html.escape(surface['repo_ref'])}</code></td>"
            f"<td><code>{html.escape(surface['surface_type'])}</code></td>"
            f"<td><code>{html.escape(governance)}</code></td></tr>"
        )
    agentplane = readiness["agentplane_run"]

    section = f"""
    <h2>Runtime evidence</h2>
    <table>
      <thead><tr><th>Artifact ID</th><th>Artifact</th><th>Ref</th><th>SHA-256 digest</th><th>Status</th></tr></thead>
      <tbody>
        {' '.join(evidence_rows)}
      </tbody>
    </table>
    <h2>Runtime readiness</h2>
    <table>
      <thead><tr><th>Signal</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>AgentPlane run ID</td><td><code>{html.escape(str(agentplane['run_id']))}</code></td></tr>
        <tr><td>AgentPlane run ref</td><td><code>{html.escape(str(agentplane['run_ref']))}</code></td></tr>
        <tr><td>AgentPlane ref</td><td><code>{html.escape(str(agentplane['agentplane_ref']))}</code></td></tr>
        <tr><td>Requested by</td><td><code>{html.escape(str(agentplane['requested_by']))}</code></td></tr>
        <tr><td>AgentPlane execution mode</td><td><code>{html.escape(str(agentplane['execution_mode']))}</code></td></tr>
        <tr><td>AgentPlane approval state</td><td><code>{html.escape(str(agentplane['approval_state']))}</code></td></tr>
        <tr><td>Node profile</td><td><code>{html.escape(str(readiness['node_profile_ref']))}</code></td></tr>
        <tr><td>Node profile digest</td><td><code>{html.escape(str(readiness['node_profile_digest']))}</code></td></tr>
        <tr><td>Dry-run mode</td><td><code>{html.escape(str(readiness['dry_run_mode']))}</code></td></tr>
        <tr><td>Validation path</td><td><code>{html.escape(str(readiness['validation_path']))}</code></td></tr>
        <tr><td>Mutated cluster</td><td><code>{html.escape(str(readiness['mutated_cluster']).lower())}</code></td></tr>
        <tr><td>Live apply allowed</td><td><code>{html.escape(str(readiness['live_apply_allowed']).lower())}</code></td></tr>
        <tr><td>Human approval required</td><td><code>{html.escape(str(readiness['requires_human_approval']).lower())}</code></td></tr>
      </tbody>
    </table>
    <table>
      <thead><tr><th>Use surface</th><th>Repo</th><th>Type</th><th>Governance</th></tr></thead>
      <tbody>
        {' '.join(surface_rows)}
      </tbody>
    </table>
"""
    html_text = html_path.read_text(encoding="utf-8")
    html_path.write_text(html_text.replace("\n  </main>", section + "\n  </main>"), encoding="utf-8")


def update(summary_path: Path, runtime_adapter: Path, runtime_dry_run: Path) -> dict[str, Any]:
    summary = load_json(summary_path)
    refs_by_id = {
        "deploy_runtime_adapter": rel(runtime_adapter if runtime_adapter.is_absolute() else ROOT / runtime_adapter),
        "deploy_runtime_dry_run_record": rel(runtime_dry_run if runtime_dry_run.is_absolute() else ROOT / runtime_dry_run),
    }
    for ref in refs_by_id.values():
        path = path_from_ref(ref)
        if not path.exists() or not path.is_file():
            raise SystemExit(f"ERR: runtime evidence artifact missing: {ref}")
    readiness = runtime_readiness(refs_by_id["deploy_runtime_adapter"], refs_by_id["deploy_runtime_dry_run_record"])

    artifacts = summary.setdefault("artifacts", {})
    artifacts.update(refs_by_id)
    checks = summary.setdefault("checks", [])
    for check in ["runtime_adapter_indexed", "runtime_dry_run_record_indexed", "runtime_readiness_summary_appended", "agentplane_run_linked"]:
        if check not in checks:
            checks.append(check)
    write_json(summary_path, summary)

    append_markdown(path_from_ref(artifacts["summary_markdown"]), refs_by_id, readiness)
    append_html(path_from_ref(artifacts["summary_html"]), refs_by_id, readiness)
    refresh_index(path_from_ref(artifacts["artifact_index"]), refs_by_id)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Add runtime evidence to a FogStack local demo")
    parser.add_argument("--summary-json", type=Path, default=Path("build/fogstack-local-demo/fogstack-local-demo.summary.json"))
    parser.add_argument("--runtime-adapter", type=Path, default=Path("build/fogstack-local-demo/deploy/fogstack.access.local-cluster-runtime-adapter.json"))
    parser.add_argument("--runtime-dry-run-record", type=Path, default=Path("build/fogstack-local-demo/deploy/fogstack.access.runtime-dry-run.record.json"))
    args = parser.parse_args()
    summary_path = args.summary_json if args.summary_json.is_absolute() else ROOT / args.summary_json
    adapter_path = args.runtime_adapter if args.runtime_adapter.is_absolute() else ROOT / args.runtime_adapter
    dry_run_path = args.runtime_dry_run_record if args.runtime_dry_run_record.is_absolute() else ROOT / args.runtime_dry_run_record
    update(summary_path, adapter_path, dry_run_path)
    print(json.dumps({"kind": "FogStackLocalDemoRuntimeEvidenceUpdate", "status": "passed", "artifact_ids": sorted(ARTIFACTS)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
