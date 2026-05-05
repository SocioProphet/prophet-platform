#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ID = "deploy_live_apply_plan_record"
ARTIFACT_LABEL = "Live apply plan record"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def path_from_ref(ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def refresh_index(index_path: Path, artifact_ref: str) -> None:
    index = load_json(index_path)
    by_id = {entry["id"]: entry for entry in index.get("artifacts", []) if isinstance(entry, dict) and entry.get("id")}
    path = path_from_ref(artifact_ref)
    if not path.exists() or not path.is_file():
        raise SystemExit(f"ERR: apply plan artifact missing: {artifact_ref}")
    by_id[ARTIFACT_ID] = {
        "id": ARTIFACT_ID,
        "ref": artifact_ref,
        "digest": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }
    index["artifacts"] = [by_id[key] for key in sorted(by_id)]
    write_json(index_path, index)


def emit_plan(deploy_plan_ref: str, live_preflight_ref: str, output_path: Path) -> dict[str, Any]:
    import subprocess
    import sys

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable,
        str(ROOT / "tools" / "emit_fogstack_live_apply_plan_record.py"),
        "--deploy-plan",
        deploy_plan_ref,
        "--live-preflight",
        live_preflight_ref,
        "--output",
        str(output_path),
    ], cwd=ROOT, check=True, capture_output=True, text=True)
    return load_json(output_path)


def append_markdown(markdown_path: Path, artifact_ref: str, record: dict[str, Any]) -> None:
    path = path_from_ref(artifact_ref)
    section = "\n".join([
        "",
        "## Live apply planning",
        "",
        "| Artifact ID | Artifact | Ref | SHA-256 digest | Status |",
        "|---|---|---|---|---|",
        f"| `{ARTIFACT_ID}` | {ARTIFACT_LABEL} | `{artifact_ref}` | `{sha256_file(path)}` | `indexed` |",
        "",
        "| Signal | Value |",
        "|---|---|",
        f"| Mode | `{record.get('mode')}` |",
        f"| Status | `{record.get('status')}` |",
        f"| Live preflight status | `{record.get('live_preflight_status')}` |",
        f"| Run performed | `{str(record.get('safety', {}).get('run_performed')).lower()}` |",
        f"| Mutated cluster | `{str(record.get('safety', {}).get('mutated_cluster')).lower()}` |",
        f"| Live apply allowed | `{str(record.get('safety', {}).get('live_apply_allowed')).lower()}` |",
        f"| Future approval required | `{str(record.get('safety', {}).get('future_approval_record_required')).lower()}` |",
        "",
    ])
    markdown_path.write_text(markdown_path.read_text(encoding="utf-8") + section, encoding="utf-8")


def append_html(html_path: Path, artifact_ref: str, record: dict[str, Any]) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    path = path_from_ref(artifact_ref)
    safety = record.get("safety", {}) if isinstance(record.get("safety"), dict) else {}
    section = f"""
    <h2>Live apply planning</h2>
    <table>
      <thead><tr><th>Artifact ID</th><th>Artifact</th><th>Ref</th><th>SHA-256 digest</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td><code>{esc(ARTIFACT_ID)}</code></td><td>{esc(ARTIFACT_LABEL)}</td><td><code>{esc(artifact_ref)}</code></td><td><code>{esc(sha256_file(path))}</code></td><td>indexed</td></tr>
      </tbody>
    </table>
    <table>
      <thead><tr><th>Signal</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>Mode</td><td><code>{esc(record.get('mode'))}</code></td></tr>
        <tr><td>Status</td><td><code>{esc(record.get('status'))}</code></td></tr>
        <tr><td>Live preflight status</td><td><code>{esc(record.get('live_preflight_status'))}</code></td></tr>
        <tr><td>Run performed</td><td><code>{esc(str(safety.get('run_performed')).lower())}</code></td></tr>
        <tr><td>Mutated cluster</td><td><code>{esc(str(safety.get('mutated_cluster')).lower())}</code></td></tr>
        <tr><td>Live apply allowed</td><td><code>{esc(str(safety.get('live_apply_allowed')).lower())}</code></td></tr>
        <tr><td>Future approval required</td><td><code>{esc(str(safety.get('future_approval_record_required')).lower())}</code></td></tr>
      </tbody>
    </table>
"""
    html_text = html_path.read_text(encoding="utf-8")
    html_path.write_text(html_text.replace("\n  </main>", section + "\n  </main>"), encoding="utf-8")


def update(summary_path: Path, output_path: Path | None) -> dict[str, Any]:
    summary = load_json(summary_path)
    artifacts = summary.setdefault("artifacts", {})
    deploy_plan_ref = artifacts.get("deploy_plan")
    preflight_ref = artifacts.get("deploy_live_cluster_preflight_record")
    if not isinstance(deploy_plan_ref, str) or not isinstance(preflight_ref, str):
        raise SystemExit("ERR: summary missing deploy plan or live preflight artifact")
    if output_path is None:
        output_path = path_from_ref(deploy_plan_ref).parent / "fogstack.access.live-apply-plan.record.json"
    output_path = output_path if output_path.is_absolute() else ROOT / output_path
    record = emit_plan(deploy_plan_ref, preflight_ref, output_path)
    artifact_ref = rel(output_path)
    artifacts[ARTIFACT_ID] = artifact_ref
    checks = summary.setdefault("checks", [])
    for check in ["live_apply_plan_record_emitted", "live_apply_plan_record_indexed", "live_apply_plan_summary_appended"]:
        if check not in checks:
            checks.append(check)
    write_json(summary_path, summary)
    refresh_index(path_from_ref(artifacts["artifact_index"]), artifact_ref)
    append_markdown(path_from_ref(artifacts["summary_markdown"]), artifact_ref, record)
    append_html(path_from_ref(artifacts["summary_html"]), artifact_ref, record)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Add plan-only live apply evidence to a FogStack local demo")
    parser.add_argument("--summary-json", type=Path, default=Path("build/fogstack-local-demo/fogstack-local-demo.summary.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary_path = args.summary_json if args.summary_json.is_absolute() else ROOT / args.summary_json
    summary = update(summary_path, args.output)
    print(json.dumps({"kind": "FogStackLocalDemoApplyPlanUpdate", "status": "passed", "artifact": summary["artifacts"][ARTIFACT_ID]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
