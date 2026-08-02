#!/usr/bin/env python3
"""Preflight (INV-DEP-9): every Rollout analysis ref must resolve in the overlay it deploys to.

Argo Rollouts `AnalysisTemplate`s are **namespaced** — a Rollout may only reference an
AnalysisTemplate that lives in ITS OWN namespace. `ClusterAnalysisTemplate`s are cluster-scoped
and resolve from any namespace (referenced with `clusterScope: true`). A Rollout that references
a namespaced template which its overlay does NOT render — or a cluster-scoped template that no
`ClusterAnalysisTemplate` in the repo declares — is a manifest that `kubectl kustomize` renders
perfectly and the LIVE Rollout controller rejects:

    InvalidSpec: AnalysisTemplate 'slo-gate' not found      (Degraded, no pods)

That is exactly what a wave-deploy hit: the prod blue-green Rollout referenced `slo-gate`, but
that AnalysisTemplate existed ONLY in the `socioprophet` namespace; deploying the prod overlay
to a fresh `prophet-platform-prod` namespace failed with no pods. Dry-run kustomize was green.
This gate makes an overlay prove it is **self-contained**: every AnalysisTemplate a Rollout
names is either rendered by the overlay itself (namespaced, same namespace) or is a declared
cluster-scoped `ClusterAnalysisTemplate` (resolvable everywhere).

Teeth both ways: tools/tests/test_verify_rollout_analysis_refs.py feeds a resolvable overlay
(passes) and a dangling ref — namespaced template not rendered, and a clusterScope ref to an
undeclared template — (fails). A gate that has only ever passed proves nothing.

Runs static (no cluster): it shells out to `kubectl kustomize` to render each overlay, then
inspects the rendered YAML. Wired into `make rollout-analysis-refs-check` (the
validate-target-diagnostics matrix) and `wave-promote.yml`.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]

ROLLOUT_KIND = "Rollout"
NS_TEMPLATE_KIND = "AnalysisTemplate"
CLUSTER_TEMPLATE_KIND = "ClusterAnalysisTemplate"

# The wave overlays this gate renders by default. Each must be self-contained: a Rollout it
# renders may only reference an AnalysisTemplate the overlay also renders, or a cluster-scoped
# ClusterAnalysisTemplate declared in the repo.
DEFAULT_OVERLAYS = [
    "infra/k8s/search-orchestrator/overlays/promote/dev",
    "infra/k8s/search-orchestrator/overlays/promote/canary",
    "infra/k8s/search-orchestrator/overlays/promote/prod",
]


def _load_docs(text: str) -> tuple[list[dict[str, Any]], str | None]:
    """Parse every YAML doc. Fail-closed: a parse error is surfaced, never swallowed — a
    manifest that will not parse cannot be certified self-contained."""
    try:
        return [d for d in yaml.safe_load_all(text) if isinstance(d, dict)], None
    except yaml.YAMLError as e:
        return [], type(e).__name__


def _analysis_blocks(spec: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield every analysis block reachable from a Rollout spec — blueGreen pre/post-promotion
    and canary top-level + per-step analyses. Each block carries a `templates:` list."""
    strategy = spec.get("strategy") or {}
    bg = strategy.get("blueGreen") or {}
    for key in ("prePromotionAnalysis", "postPromotionAnalysis"):
        blk = bg.get(key)
        if isinstance(blk, dict):
            yield blk
    canary = strategy.get("canary") or {}
    top = canary.get("analysis")
    if isinstance(top, dict):
        yield top
    for step in canary.get("steps") or []:
        if isinstance(step, dict) and isinstance(step.get("analysis"), dict):
            yield step["analysis"]


def rollout_analysis_refs(doc: dict[str, Any]) -> list[tuple[str, bool]]:
    """(templateName, cluster_scoped) for every analysis-template ref in a Rollout doc."""
    refs: list[tuple[str, bool]] = []
    spec = doc.get("spec") or {}
    for block in _analysis_blocks(spec):
        for tmpl in block.get("templates") or []:
            if not isinstance(tmpl, dict):
                continue
            name = tmpl.get("templateName")
            if name:
                refs.append((str(name), bool(tmpl.get("clusterScope", False))))
    return refs


def rendered_templates(docs: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """Names of (namespaced AnalysisTemplates, ClusterAnalysisTemplates) present in a doc set."""
    ns: set[str] = set()
    cluster: set[str] = set()
    for d in docs:
        name = (d.get("metadata") or {}).get("name")
        if not name:
            continue
        if d.get("kind") == NS_TEMPLATE_KIND:
            ns.add(str(name))
        elif d.get("kind") == CLUSTER_TEMPLATE_KIND:
            cluster.add(str(name))
    return ns, cluster


def ref_violations(
    docs: list[dict[str, Any]],
    declared_cluster_templates: set[str],
    where: str,
) -> list[str]:
    """Every Rollout analysis ref in `docs` must resolve: a namespaced ref against templates
    rendered in this SAME overlay; a clusterScope ref against a declared ClusterAnalysisTemplate
    (or one rendered in the set)."""
    rendered_ns, rendered_cluster = rendered_templates(docs)
    resolvable_cluster = declared_cluster_templates | rendered_cluster
    out: list[str] = []
    for d in docs:
        if d.get("kind") != ROLLOUT_KIND:
            continue
        rname = (d.get("metadata") or {}).get("name", "<unnamed>")
        for tmpl_name, cluster_scoped in rollout_analysis_refs(d):
            if cluster_scoped:
                if tmpl_name not in resolvable_cluster:
                    out.append(
                        f"{where}: Rollout '{rname}' references clusterScope template "
                        f"'{tmpl_name}', but no ClusterAnalysisTemplate '{tmpl_name}' is declared "
                        f"in the repo — the live Rollout would be InvalidSpec "
                        f"(declare it in infra/k8s/rollouts/base or drop clusterScope)."
                    )
            else:
                if tmpl_name not in rendered_ns:
                    out.append(
                        f"{where}: Rollout '{rname}' references namespaced AnalysisTemplate "
                        f"'{tmpl_name}', but this overlay does not render it — an apply to a fresh "
                        f"namespace fails 'InvalidSpec: AnalysisTemplate {tmpl_name!r} not found' "
                        f"(bundle a namespaced AnalysisTemplate '{tmpl_name}' into this overlay, "
                        f"or make it a ClusterAnalysisTemplate and set clusterScope: true)."
                    )
    return out


def scan_rendered(
    text: str,
    declared_cluster_templates: set[str] | None = None,
    where: str = "<rendered>",
) -> list[str]:
    """Parse rendered multi-doc YAML and return analysis-ref violations. The test seam."""
    docs, err = _load_docs(text)
    if err is not None:
        return [f"{where}: rendered output is not valid YAML ({err}); cannot certify self-contained"]
    return ref_violations(docs, declared_cluster_templates or set(), where)


def discover_cluster_templates(root: Path) -> set[str]:
    """Every ClusterAnalysisTemplate name declared anywhere in the repo. These are cluster-scoped
    (applied once cluster-wide) so a clusterScope ref resolves against them from any namespace.
    Helm template dirs are skipped (they are not concrete manifests); unparseable files are
    ignored here — the fail-closed parse guard applies to the RENDERED overlay, not to sources
    scanned for declarations."""
    names: set[str] = set()
    for path in root.rglob("*.y*ml"):
        parts = path.parts
        if "templates" in parts and "charts" in parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if CLUSTER_TEMPLATE_KIND not in text:
            continue
        try:
            docs = [d for d in yaml.safe_load_all(text) if isinstance(d, dict)]
        except yaml.YAMLError:
            continue
        for d in docs:
            if d.get("kind") == CLUSTER_TEMPLATE_KIND:
                name = (d.get("metadata") or {}).get("name")
                if name:
                    names.add(str(name))
    return names


def render_overlay(overlay: Path) -> tuple[str, str | None]:
    """Render an overlay via `kubectl kustomize`. Returns (stdout, error) — a non-zero exit is a
    fail-closed error, not swallowed."""
    try:
        proc = subprocess.run(
            ["kubectl", "kustomize", str(overlay)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "", "kubectl not found (needed to render the overlay)"
    if proc.returncode != 0:
        return "", f"kubectl kustomize failed (exit {proc.returncode}): {proc.stderr.strip()}"
    return proc.stdout, None


def check_overlays(root: Path, overlays: list[str]) -> list[str]:
    declared = discover_cluster_templates(root)
    violations: list[str] = []
    for rel in overlays:
        overlay = root / rel
        if not overlay.exists():
            violations.append(f"{rel}: overlay path does not exist")
            continue
        text, err = render_overlay(overlay)
        if err is not None:
            violations.append(f"{rel}: {err}")
            continue
        violations.extend(scan_rendered(text, declared, where=rel))
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "overlays",
        nargs="*",
        default=DEFAULT_OVERLAYS,
        help="overlay dirs to render + check (default: the search-orchestrator promote waves)",
    )
    args = ap.parse_args(argv)
    overlays = args.overlays or DEFAULT_OVERLAYS
    violations = check_overlays(ROOT, overlays)
    if violations:
        print("Rollout analysis-ref check FAILED (INV-DEP-9):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    declared = discover_cluster_templates(ROOT)
    print(
        f"OK: {len(overlays)} overlay(s) render self-contained analysis refs "
        f"(declared ClusterAnalysisTemplates: {sorted(declared) or 'none'})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
