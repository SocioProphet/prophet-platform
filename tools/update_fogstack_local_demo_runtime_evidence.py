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


def append_markdown(markdown_path: Path, refs_by_id: dict[str, str]) -> None:
    rows = []
    for artifact_id, label in ARTIFACTS.items():
        ref = refs_by_id[artifact_id]
        digest = sha256_file(path_from_ref(ref))
        rows.append(f"| `{artifact_id}` | {label} | `{ref}` | `{digest}` | `indexed` |")
    section = "\n".join([
        "",
        "## Runtime evidence",
        "",
        "| Artifact ID | Artifact | Ref | SHA-256 digest | Status |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ])
    markdown_path.write_text(markdown_path.read_text(encoding="utf-8") + section, encoding="utf-8")


def append_html(html_path: Path, refs_by_id: dict[str, str]) -> None:
    rows = []
    for artifact_id, label in ARTIFACTS.items():
        ref = refs_by_id[artifact_id]
        digest = sha256_file(path_from_ref(ref))
        rows.append(
            f"<tr><td><code>{html.escape(artifact_id)}</code></td>"
            f"<td>{html.escape(label)}</td>"
            f"<td><code>{html.escape(ref)}</code></td>"
            f"<td><code>{html.escape(digest)}</code></td>"
            "<td>indexed</td></tr>"
        )
    section = f"""
    <h2>Runtime evidence</h2>
    <table>
      <thead><tr><th>Artifact ID</th><th>Artifact</th><th>Ref</th><th>SHA-256 digest</th><th>Status</th></tr></thead>
      <tbody>
        {' '.join(rows)}
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

    artifacts = summary.setdefault("artifacts", {})
    artifacts.update(refs_by_id)
    checks = summary.setdefault("checks", [])
    for check in ["runtime_adapter_indexed", "runtime_dry_run_record_indexed"]:
        if check not in checks:
            checks.append(check)
    write_json(summary_path, summary)

    append_markdown(path_from_ref(artifacts["summary_markdown"]), refs_by_id)
    append_html(path_from_ref(artifacts["summary_html"]), refs_by_id)
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
