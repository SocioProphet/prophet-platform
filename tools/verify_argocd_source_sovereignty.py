#!/usr/bin/env python3
"""Sovereignty gate for ArgoCD Application sources.

Every ArgoCD `Application` in this repo should pull from a sovereign source — our own git
(`github.com/SocioProphet/*`, `github.com/SourceOS-Linux/*`) or the sovereign registry
(`*.socioprophet.ai`) — not a public Helm CDN. A foundation-tier component fetched over an
unpinned third-party index (`kyverno.github.io`, `grafana.github.io`, …) is a supply-chain
dependency the estate does not control; pointedly, the kyverno controller that is meant to
*enforce* image provenance is itself pulled from `kyverno.github.io`.

Rather than break CI on the ~6 charts already sourced that way, this is a SHRINK-ONLY ratchet,
the same discipline as the moving-tag ratchet in preflight_deploy_contract.py:

  * a NEW external source (not in KNOWN_BROKEN) FAILS the build;
  * a KNOWN_BROKEN entry that no longer appears in the tree FAILS too — it has been migrated
    (or removed), so it must be deleted from the list; the ratchet can only tighten.

Each KNOWN_BROKEN entry names why it is still external and the migration target (vendor the
chart into the sovereign registry, digest-pinned). Self-excluding: this validator is not an
Application manifest, so it never scans itself. Its teeth are proven every run by a hermetic
self-test (a synthetic new external source MUST fail; an all-migrated tree MUST fail on the
stale allowlist entry).

  verify_argocd_source_sovereignty.py         # scan deploy/argocd + infra/argocd
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["deploy/argocd", "infra/argocd"]

# A source is sovereign if its repoURL starts with one of these.
SOVEREIGN_PREFIXES = (
    "https://github.com/SocioProphet/",
    "https://github.com/SourceOS-Linux/",
    "https://registry.socioprophet.ai",
    "https://zot.socioprophet.ai",
)

# Shrink-only allowlist: external sources that exist TODAY. Each must be migrated to the
# sovereign registry (vendor the chart, pin by digest) and then deleted from this list. Do not
# add to it — a new external source is meant to fail. Tracked: prophet-platform #1343.
KNOWN_BROKEN: dict[str, str] = {
    "https://kyverno.github.io/kyverno": "policy engine; vendor to zot — #1343",
    "https://grafana.github.io/helm-charts": "loki/grafana observability charts; vendor to zot",
    "https://prometheus-community.github.io/helm-charts": "kube-prometheus-stack; vendor to zot",
    "https://kedacore.github.io/charts": "KEDA autoscaling; vendor to zot",
    "https://charts.chaos-mesh.org": "chaos-mesh; vendor to zot",
    "https://argoproj.github.io/argo-helm": "argo-rollouts/argo-helm; vendor to zot",
}


def _is_sovereign(repo_url: str) -> bool:
    return any(repo_url.startswith(p) for p in SOVEREIGN_PREFIXES)


def _iter_sources(doc: dict):
    """Yield every repoURL in an Application (single .spec.source or multi .spec.sources)."""
    spec = (doc or {}).get("spec") or {}
    src = spec.get("source")
    if isinstance(src, dict) and src.get("repoURL"):
        yield str(src["repoURL"]).rstrip("/")
    for s in (spec.get("sources") or []):
        if isinstance(s, dict) and s.get("repoURL"):
            yield str(s["repoURL"]).rstrip("/")


def scan(root: Path) -> dict[str, list[str]]:
    """Return {repoURL: [app names]} for every external (non-sovereign) source found."""
    external: dict[str, list[str]] = {}
    for rel in SCAN_DIRS:
        d = root / rel
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*.yaml")):
            try:
                docs = list(yaml.safe_load_all(path.read_text()))
            except (yaml.YAMLError, OSError):
                continue
            for doc in docs:
                if not isinstance(doc, dict) or doc.get("kind") != "Application":
                    continue
                name = (doc.get("metadata") or {}).get("name", path.name)
                for repo in _iter_sources(doc):
                    if not _is_sovereign(repo):
                        external.setdefault(repo, []).append(name)
    return external


def evaluate(external: dict[str, list[str]], known: dict[str, str]) -> list[str]:
    """Ratchet logic → list of problems (empty = pass)."""
    problems: list[str] = []
    for repo, apps in sorted(external.items()):
        if repo.rstrip("/") not in {k.rstrip("/") for k in known}:
            problems.append(f"NEW external source (not sovereign, not allowlisted): {repo}  "
                            f"[apps: {', '.join(sorted(set(apps)))}] — vendor it to the sovereign registry")
    seen = {r.rstrip("/") for r in external}
    for repo in sorted(known):
        if repo.rstrip("/") not in seen:
            problems.append(f"STALE allowlist entry: {repo} no longer appears — it was migrated/removed; "
                            f"delete it from KNOWN_BROKEN (the ratchet only shrinks)")
    return problems


def _self_test() -> bool:
    checks = [
        ("sovereign git passes", _is_sovereign("https://github.com/SocioProphet/prophet-platform")),
        ("sovereign registry passes", _is_sovereign("https://registry.socioprophet.ai/charts")),
        ("public CDN is external", not _is_sovereign("https://kyverno.github.io/kyverno")),
        ("new external source fails",
         evaluate({"https://evil.example.com/chart": ["x"]}, {}) != []),
        ("known external source passes",
         evaluate({"https://kyverno.github.io/kyverno": ["kyverno"]},
                  {"https://kyverno.github.io/kyverno": "r"}) == []),
        ("stale allowlist entry fails",
         evaluate({}, {"https://gone.github.io/x": "r"}) != []),
    ]
    ok = all(v for _, v in checks)
    for name, v in checks:
        print(f"    {'OK  ' if v else 'FAIL'} self-test: {name}")
    return ok


def main() -> int:
    if not _self_test():
        print("FAIL: self-test did not pass — the sovereignty gate has no teeth")
        return 2
    external = scan(ROOT)
    problems = evaluate(external, KNOWN_BROKEN)
    if problems:
        print(f"FAIL: {len(problems)} ArgoCD source-sovereignty problem(s):")
        for p in problems:
            print(f"  {p}")
        return 1
    n_ext = len(external)
    print(f"OK: every ArgoCD Application source is sovereign or a shrinking KNOWN_BROKEN entry "
          f"({n_ext} external chart(s) still to migrate: {', '.join(sorted(external)) or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
