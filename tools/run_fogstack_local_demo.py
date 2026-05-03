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

PACKS: dict[str, dict[str, str]] = {
    "access": {
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "bundle": "bundles/fogstack.access-v0.1.yaml",
        "manifest": "releases/manifests/fogstack.access-v0.1.manifest.json",
    },
    "knowledge": {
        "bundle_id": "fogstack.knowledge",
        "version": "0.1.0",
        "bundle": "bundles/fogstack.knowledge-v0.1.yaml",
        "manifest": "releases/manifests/fogstack.knowledge-v0.1.manifest.json",
    },
    "evaluation": {
        "bundle_id": "fogstack.evaluation",
        "version": "0.1.0",
        "bundle": "bundles/fogstack.evaluation-v0.1.yaml",
        "manifest": "releases/manifests/fogstack.evaluation-v0.1.manifest.json",
    },
}
PACK_ALIASES: dict[str, list[str]] = {
    "access": ["access"],
    "knowledge": ["knowledge"],
    "evaluation": ["evaluation"],
    "all": ["access", "knowledge", "evaluation"],
}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(cmd: list[str], *, stdout: Path | None = None) -> None:
    if stdout:
        stdout.parent.mkdir(parents=True, exist_ok=True)
        with stdout.open("w", encoding="utf-8") as handle:
            subprocess.run(cmd, cwd=ROOT, check=True, stdout=handle)
    else:
        subprocess.run(cmd, cwd=ROOT, check=True)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def pack_configs(pack: str) -> list[dict[str, str]]:
    if pack not in PACK_ALIASES:
        raise SystemExit(f"ERR: unsupported FogStack local demo pack: {pack}")
    return [PACKS[name] | {"pack": name} for name in PACK_ALIASES[pack]]


def output_dirs(output_dir: Path) -> dict[str, Path]:
    return {
        "validation": output_dir / "validation",
        "publication": output_dir / "publication",
        "promoted": output_dir / "promoted",
        "approval": output_dir / "approval",
        "gate": output_dir / "gate",
        "registry_publication": output_dir / "registry-publication",
        "registry_root": output_dir / "registry",
        "lifecycle": output_dir / "lifecycle",
        "root": output_dir / "root",
    }


def build_demo(pack: str, output_dir: Path, clean: bool) -> dict[str, Any]:
    selected = pack_configs(pack)

    support_catalog = ROOT / "catalog" / "fogstack-support-states-v0.1.yaml"
    promotion_policy = ROOT / "catalog" / "fogstack-manifest-promotion-policy-v0.1.yaml"
    approver_policy = ROOT / "catalog" / "fogstack-manifest-promotion-approver-policy-v0.1.yaml"
    publication_gate_policy = ROOT / "catalog" / "fogstack-release-publication-gate-policy-v0.1.yaml"

    required = [support_catalog, promotion_policy, approver_policy, publication_gate_policy]
    for cfg in selected:
        required.extend([ROOT / cfg["bundle"], ROOT / cfg["manifest"]])
    missing = [path for path in required if not path.exists()]
    if missing:
        raise SystemExit("ERR: missing local demo inputs: " + ", ".join(rel(path) for path in missing))

    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dirs = output_dirs(output_dir)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    release_summaries: list[dict[str, Any]] = []
    validation_records: list[Path] = []
    manifest_paths: list[Path] = []

    for cfg in selected:
        bundle_id = cfg["bundle_id"]
        version = cfg["version"]
        bundle = ROOT / cfg["bundle"]
        manifest = ROOT / cfg["manifest"]
        manifest_paths.append(manifest)

        verify_json = dirs["validation"] / f"{bundle_id}.verify.json"
        validation_record = dirs["validation"] / f"{bundle_id}.validation.record.json"
        validation_records.append(validation_record)

        run([
            sys.executable,
            "tools/fogstack_verify.py",
            str(bundle),
            "--json",
        ], stdout=verify_json)

        run([
            sys.executable,
            "tools/emit_fogstack_validation_record.py",
            "--verifier-json", str(verify_json),
            "--bundle-id", bundle_id,
            "--version", version,
            "--source", "local",
            "--evidence-ref", rel(verify_json),
            "--output", str(validation_record),
        ])

        release_summaries.append({
            "pack": cfg["pack"],
            "bundle_id": bundle_id,
            "version": version,
            "verify_json": rel(verify_json),
            "validation_record": rel(validation_record),
        })

    publication_cmd = [
        sys.executable,
        "tools/build_fogstack_manifest_publication_set.py",
        "--output-dir", str(dirs["publication"]),
        "--signature-type", "other",
        "--signature-ref-prefix", "artifact://local-demo/signatures",
    ]
    for manifest in manifest_paths:
        publication_cmd.extend(["--manifest", str(manifest)])
    run(publication_cmd)

    run([
        sys.executable,
        "tools/promote_fogstack_manifest_publication_set.py",
        "--input-dir", str(dirs["publication"]),
        "--output-dir", str(dirs["promoted"]),
        "--support-catalog", str(support_catalog),
        "--target-channel", "candidate",
        "--target-support-state", "supported",
    ])

    promoted_set = dirs["promoted"] / "manifest-publication-set.json"
    run([
        sys.executable,
        "tools/check_fogstack_manifest_promotion_policy.py",
        "--publication-set", str(promoted_set),
        "--policy-catalog", str(promotion_policy),
    ])

    approval_record = dirs["approval"] / "fogstack.manifest-promotion.approval.record.json"
    approval_sig = dirs["approval"] / "fogstack.manifest-promotion.approval.sig"
    approval_private = dirs["approval"] / "private.pem"
    approval_public = dirs["approval"] / "public.pem"
    approval_verification = dirs["approval"] / "fogstack.manifest-promotion.approval.signature-verification.json"

    run([
        sys.executable,
        "tools/emit_fogstack_manifest_promotion_approval_record.py",
        "--promotion-set", str(promoted_set),
        "--required-approvals", "2",
        "--approval", "release-manager:release-manager:approved local demo candidate promotion",
        "--approval", "security-reviewer:security-reviewer:approved local demo release evidence",
        "--signature-type", "other",
        "--signature-ref", str(approval_sig),
        "--output", str(approval_record),
    ])

    run([
        sys.executable,
        "tools/check_fogstack_manifest_promotion_approval_record.py",
        "--approval-record", str(approval_record),
        "--promotion-set", str(promoted_set),
        "--require-signed",
    ])
    run([
        sys.executable,
        "tools/check_fogstack_manifest_promotion_approver_policy.py",
        "--approval-record", str(approval_record),
        "--approver-policy", str(approver_policy),
    ])

    run(["openssl", "genpkey", "-algorithm", "RSA", "-out", str(approval_private)])
    run(["openssl", "pkey", "-in", str(approval_private), "-pubout", "-out", str(approval_public)])
    run([
        "openssl", "dgst", "-sha256",
        "-sign", str(approval_private),
        "-out", str(approval_sig),
        str(approval_record),
    ])
    run([
        sys.executable,
        "tools/run_openssl_fogstack_manifest_promotion_approval_verifier.py",
        "--approval-record", str(approval_record),
        "--signature", str(approval_sig),
        "--public-key", str(approval_public),
        "--key-ref", str(approval_public),
        "--output", str(approval_verification),
    ])

    release_identity = dirs["gate"] / "release-identity.json"
    write_json(release_identity, {
        "kind": "FogStackReleaseIdentity",
        "schema_version": "v0.1",
        "id": "github-actions",
        "issuer": "github-actions",
        "subject": "SocioProphet/prophet-platform/.github/workflows/fogstack-manifest-promotion.yml",
    })

    publication_gate = dirs["gate"] / "fogstack.release-publication-gate.record.json"
    run([
        sys.executable,
        "tools/emit_fogstack_release_publication_gate_record.py",
        "--publication-set", str(promoted_set),
        "--approval-record", str(approval_record),
        "--approval-signature-verification", str(approval_verification),
        "--release-identity", str(release_identity),
        "--policy-catalog", str(publication_gate_policy),
        "--output", str(publication_gate),
    ])

    registry_index = dirs["registry_publication"] / "registry-publication.index.json"
    registry_cmd = [
        sys.executable,
        "tools/build_fogstack_registry_publication_index.py",
        "--registry-uri", f"file://{rel(dirs['registry_root'])}",
        "--publication-set", str(promoted_set),
        "--publication-gate-record", str(publication_gate),
        "--artifact", "manifest-publication-set", str(promoted_set),
        "--artifact", "approval-record", str(approval_record),
        "--artifact", "approval-signature-verification", str(approval_verification),
        "--artifact", "release-publication-gate", str(publication_gate),
    ]
    for validation_record in validation_records:
        registry_cmd.extend(["--artifact", "validation-record", str(validation_record)])
    registry_cmd.extend([
        "--notes", f"local demo filesystem registry publication for {pack}",
        "--output", str(registry_index),
    ])
    run(registry_cmd)

    release_root_args: list[str] = []
    for cfg, release_summary in zip(selected, release_summaries, strict=True):
        bundle_id = cfg["bundle_id"]
        version = cfg["version"]
        run([
            sys.executable,
            "tools/publish_fogstack_filesystem_registry.py",
            "--index", str(registry_index),
            "--registry-root", str(dirs["registry_root"]),
            "--bundle-id", bundle_id,
            "--version", version,
        ], stdout=dirs["registry_publication"] / f"{bundle_id}.release-pointer.json")
        run([
            sys.executable,
            "tools/check_fogstack_filesystem_registry.py",
            "--registry-root", str(dirs["registry_root"]),
            "--bundle-id", bundle_id,
            "--version", version,
        ])
        release_root = dirs["registry_root"] / bundle_id / version
        release_summary["filesystem_release_pointer"] = rel(release_root / "release-pointer.json")
        release_root_args.extend(["--release", bundle_id, version, str(release_root)])

    revocation_index = dirs["lifecycle"] / "registry-revocation-index.json"
    run([
        sys.executable,
        "tools/build_fogstack_registry_revocation_index.py",
        "--output", str(revocation_index),
    ])
    run([
        sys.executable,
        "tools/check_fogstack_registry_revocation_index.py",
        "--index", str(revocation_index),
    ])

    registry_root_metadata = dirs["root"] / "registry-root-metadata.json"
    root_cmd = [
        sys.executable,
        "tools/build_fogstack_registry_root_metadata.py",
        "--registry-uri", f"file://{rel(dirs['registry_root'])}",
        *release_root_args,
        "--revocation-index", str(revocation_index),
        "--signature-type", "other",
        "--signature-ref", "artifact://local-demo/registry-root.sig",
        "--output", str(registry_root_metadata),
    ]
    run(root_cmd)
    run([
        sys.executable,
        "tools/check_fogstack_registry_root_metadata.py",
        "--root", str(registry_root_metadata),
        "--require-signed",
    ])

    summary_path = output_dir / "fogstack-local-demo.summary.json"
    summary_markdown = output_dir / "fogstack-local-demo.summary.md"
    summary_html = output_dir / "index.html"
    artifacts: dict[str, Any] = {
        "summary_json": rel(summary_path),
        "summary_markdown": rel(summary_markdown),
        "summary_html": rel(summary_html),
        "publication_set": rel(dirs["publication"] / "manifest-publication-set.json"),
        "promoted_publication_set": rel(promoted_set),
        "approval_record": rel(approval_record),
        "approval_signature_verification": rel(approval_verification),
        "publication_gate": rel(publication_gate),
        "registry_publication_index": rel(registry_index),
        "revocation_index": rel(revocation_index),
        "registry_root_metadata": rel(registry_root_metadata),
    }
    if len(release_summaries) == 1:
        artifacts["verify_json"] = release_summaries[0]["verify_json"]
        artifacts["validation_record"] = release_summaries[0]["validation_record"]
        artifacts["filesystem_release_pointer"] = release_summaries[0]["filesystem_release_pointer"]

    summary = {
        "kind": "FogStackLocalDemoRun",
        "schema_version": "v0.1",
        "pack": pack,
        "packs": [item["pack"] for item in release_summaries],
        "bundle_id": release_summaries[0]["bundle_id"] if len(release_summaries) == 1 else None,
        "version": release_summaries[0]["version"] if len(release_summaries) == 1 else "0.1.0",
        "registry_uri": f"file://{rel(dirs['registry_root'])}",
        "channel": "candidate",
        "support_state": "supported",
        "releases": release_summaries,
        "artifacts": artifacts,
        "checks": [
            "bundle_verified",
            "validation_record_emitted",
            "publication_set_built",
            "promotion_policy_passed",
            "approval_record_checked",
            "approval_signature_verified",
            "publication_gate_passed",
            "registry_index_built",
            "filesystem_registry_published",
            "filesystem_registry_checked",
            "revocation_index_checked",
            "registry_root_checked",
        ],
    }
    write_json(summary_path, summary)
    write_text(summary_markdown, render_summary_markdown(summary))
    write_text(summary_html, render_summary_html(summary))
    return summary


def render_summary_text(summary: dict[str, Any]) -> str:
    release_lines = [
        f"- {release['bundle_id']}@{release['version']} ({release['pack']})"
        for release in summary.get("releases", [])
    ]
    artifact_paths = summary.get("artifacts", {})
    lines = [
        "FogStack local demo passed.",
        f"Pack selection: {summary.get('pack')}",
        f"Release count: {len(summary.get('releases', []))}",
        "Releases:",
        *release_lines,
        f"Channel/support: {summary.get('channel')}/{summary.get('support_state')}",
        f"Registry URI: {summary.get('registry_uri')}",
        f"Publication gate: {artifact_paths.get('publication_gate')}",
        f"Registry root metadata: {artifact_paths.get('registry_root_metadata')}",
        f"Summary JSON: {artifact_paths.get('summary_json')}",
        f"Summary Markdown: {artifact_paths.get('summary_markdown')}",
        f"Summary HTML: {artifact_paths.get('summary_html')}",
        f"Checks passed: {len(summary.get('checks', []))}",
    ]
    return "\n".join(lines) + "\n"


def render_summary_markdown(summary: dict[str, Any]) -> str:
    artifacts = summary.get("artifacts", {})
    release_rows = [
        f"| `{release['bundle_id']}` | `{release['version']}` | `{release['pack']}` | `{release['validation_record']}` | `{release['filesystem_release_pointer']}` |"
        for release in summary.get("releases", [])
    ]
    check_rows = [f"- `{check}`" for check in summary.get("checks", [])]
    lines = [
        "# FogStack Local Demo Summary",
        "",
        "## Result",
        "",
        "Status: **passed**",
        f"Pack selection: `{summary.get('pack')}`",
        f"Release count: **{len(summary.get('releases', []))}**",
        f"Channel/support: `{summary.get('channel')}/{summary.get('support_state')}`",
        f"Registry URI: `{summary.get('registry_uri')}`",
        "",
        "## Releases",
        "",
        "| Bundle | Version | Pack | Validation record | Filesystem release pointer |",
        "|---|---:|---|---|---|",
        *release_rows,
        "",
        "## Key artifacts",
        "",
        f"- Publication gate: `{artifacts.get('publication_gate')}`",
        f"- Registry root metadata: `{artifacts.get('registry_root_metadata')}`",
        f"- Registry publication index: `{artifacts.get('registry_publication_index')}`",
        f"- Revocation index: `{artifacts.get('revocation_index')}`",
        f"- Summary JSON: `{artifacts.get('summary_json')}`",
        f"- Summary HTML: `{artifacts.get('summary_html')}`",
        "",
        "## Checks",
        "",
        *check_rows,
        "",
    ]
    return "\n".join(lines)


def render_summary_html(summary: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    artifacts = summary.get("artifacts", {})
    release_rows = "\n".join(
        "<tr>"
        f"<td>{esc(release['bundle_id'])}</td>"
        f"<td>{esc(release['version'])}</td>"
        f"<td>{esc(release['pack'])}</td>"
        f"<td><code>{esc(release['validation_record'])}</code></td>"
        f"<td><code>{esc(release['filesystem_release_pointer'])}</code></td>"
        "</tr>"
        for release in summary.get("releases", [])
    )
    check_items = "\n".join(f"<li><code>{esc(check)}</code></li>" for check in summary.get("checks", []))
    artifact_items = "\n".join(
        f"<li><strong>{esc(label)}:</strong> <code>{esc(path)}</code></li>"
        for label, path in [
            ("Publication gate", artifacts.get("publication_gate")),
            ("Registry root metadata", artifacts.get("registry_root_metadata")),
            ("Registry publication index", artifacts.get("registry_publication_index")),
            ("Revocation index", artifacts.get("revocation_index")),
            ("Summary JSON", artifacts.get("summary_json")),
            ("Summary Markdown", artifacts.get("summary_markdown")),
        ]
    )
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>FogStack Local Demo Summary</title>
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
    <h1>FogStack Local Demo Summary</h1>
    <p class=\"status\">Status: passed</p>
    <dl>
      <dt>Pack selection</dt><dd><code>{esc(summary.get('pack'))}</code></dd>
      <dt>Release count</dt><dd>{esc(len(summary.get('releases', [])))}</dd>
      <dt>Channel/support</dt><dd><code>{esc(summary.get('channel'))}/{esc(summary.get('support_state'))}</code></dd>
      <dt>Registry URI</dt><dd><code>{esc(summary.get('registry_uri'))}</code></dd>
    </dl>

    <h2>Releases</h2>
    <table>
      <thead><tr><th>Bundle</th><th>Version</th><th>Pack</th><th>Validation record</th><th>Filesystem release pointer</th></tr></thead>
      <tbody>
        {release_rows}
      </tbody>
    </table>

    <h2>Key artifacts</h2>
    <ul>
      {artifact_items}
    </ul>

    <h2>Checks</h2>
    <ul>
      {check_items}
    </ul>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local FogStack release/registry demo end to end")
    parser.add_argument("--pack", choices=sorted(PACK_ALIASES), default="access")
    parser.add_argument("--output-dir", type=Path, default=Path("build/fogstack-local-demo"))
    parser.add_argument("--no-clean", action="store_true", help="Do not remove the output directory before running")
    parser.add_argument("--summary", action="store_true", help="Print a compact human-readable summary instead of JSON")
    args = parser.parse_args()

    summary = build_demo(args.pack, args.output_dir, clean=not args.no_clean)
    if args.summary:
        print(render_summary_text(summary), end="")
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
