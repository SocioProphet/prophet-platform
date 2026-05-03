#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ID = "deploy_gitops_readiness_record"
LABEL = "GitOps readiness record"


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


def add_index_entry(index_path: Path, artifact_ref: str) -> None:
    index = load_json(index_path)
    artifact_path = path_from_ref(artifact_ref)
    if not artifact_path.exists() or not artifact_path.is_file():
        raise SystemExit(f"ERR: GitOps readiness artifact missing: {artifact_ref}")
    entries = [entry for entry in index.get("artifacts", []) if entry.get("id") != ARTIFACT_ID]
    entries.append({
        "id": ARTIFACT_ID,
        "ref": artifact_ref,
        "digest": sha256_file(artifact_path),
        "size_bytes": artifact_path.stat().st_size,
    })
    index["artifacts"] = entries
    write_json(index_path, index)


def append_markdown(markdown_path: Path, artifact_ref: str, digest: str) -> None:
    section = "\n".join([
        "",
        "## GitOps readiness",
        "",
        "| Artifact ID | Artifact | Ref | SHA-256 digest | Status |",
        "|---|---|---|---|---|",
        f"| `{ARTIFACT_ID}` | {LABEL} | `{artifact_ref}` | `{digest}` | `indexed` |",
        "",
    ])
    markdown_path.write_text(markdown_path.read_text(encoding="utf-8") + section, encoding="utf-8")


def append_html(html_path: Path, artifact_ref: str, digest: str) -> None:
    section = f"""
    <h2>GitOps readiness</h2>
    <table>
      <thead><tr><th>Artifact ID</th><th>Artifact</th><th>Ref</th><th>SHA-256 digest</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td><code>{html.escape(ARTIFACT_ID)}</code></td><td>{html.escape(LABEL)}</td><td><code>{html.escape(artifact_ref)}</code></td><td><code>{html.escape(digest)}</code></td><td>indexed</td></tr>
      </tbody>
    </table>
"""
    html_text = html_path.read_text(encoding="utf-8")
    html_path.write_text(html_text.replace("\n  </main>", section + "\n  </main>"), encoding="utf-8")


def update(summary_path: Path, gitops_record: Path) -> dict[str, Any]:
    summary = load_json(summary_path)
    artifact_ref = rel(gitops_record if gitops_record.is_absolute() else ROOT / gitops_record)
    artifact_path = path_from_ref(artifact_ref)
    digest = sha256_file(artifact_path)

    artifacts = summary.setdefault("artifacts", {})
    artifacts[ARTIFACT_ID] = artifact_ref
    checks = summary.setdefault("checks", [])
    if "gitops_readiness_record_indexed" not in checks:
        checks.append("gitops_readiness_record_indexed")
    write_json(summary_path, summary)

    add_index_entry(path_from_ref(artifacts["artifact_index"]), artifact_ref)
    append_markdown(path_from_ref(artifacts["summary_markdown"]), artifact_ref, digest)
    append_html(path_from_ref(artifacts["summary_html"]), artifact_ref, digest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Add GitOps readiness evidence to a FogStack local demo")
    parser.add_argument("--summary-json", type=Path, default=Path("build/fogstack-local-demo/fogstack-local-demo.summary.json"))
    parser.add_argument("--gitops-readiness-record", type=Path, default=Path("build/fogstack-local-demo/deploy/fogstack.access.gitops-readiness.record.json"))
    args = parser.parse_args()
    summary_path = args.summary_json if args.summary_json.is_absolute() else ROOT / args.summary_json
    record_path = args.gitops_readiness_record if args.gitops_readiness_record.is_absolute() else ROOT / args.gitops_readiness_record
    update(summary_path, record_path)
    print(json.dumps({"kind": "FogStackLocalDemoGitOpsReadinessUpdate", "status": "passed", "artifact_id": ARTIFACT_ID}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
