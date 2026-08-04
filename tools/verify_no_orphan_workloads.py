#!/usr/bin/env python3
"""LAYER 2 (detect) of the orphan-workload remediation (2026-08-04 gitea postmortem).

GitOps (ArgoCD) only reconciles what it MANAGES. A workload applied out-of-band — a human
`kubectl apply`, or a CI workflow doing `kubectl apply` — is INVISIBLE to ArgoCD: no drift, no
prune, no alert. So a broken out-of-band workload (the gitea git server) can crashloop in prod
indefinitely and every GitOps signal stays green. That is the inverse defect: *enforced ≠
declared* — a thing running that no continuously-reconciled declaration owns.

This detector closes that blind spot: it lists workloads and FAILS on any that is neither
ArgoCD/Helm-managed nor on the shrink-only SANCTIONED_OUT_OF_BAND allowlist. A NEW out-of-band
workload fails the gate; a sanctioned one that has since moved under ArgoCD must be removed from
the allowlist (the ratchet only tightens — every workload should end up GitOps-managed).

Allowlist entries and the live scan are NAMESPACE-QUALIFIED (`"<namespace>/<name>"`). This is not
cosmetic: the scm-namespace `gitea` (code.socioprophet.ai, 125 real repos) and the socioprophet-
namespace `gitea` (gitea.sourceos.dev, empty) are two ENTIRELY SEPARATE Deployments that happen to
share the bare name "gitea" — a bare-name allowlist would silently conflate them, sanctioning one
by accident of string equality with the other. See docs/postmortems/2026-08-04-orphan-gitea-crashloop.md
for the original 2-workload finding, and deploy/scm/gitea-sovereign.yaml for how the THIRD one —
invisible to this detector for 20 days because it defaulted to `--namespace socioprophet` and
nothing ever pointed it at `scm` — was found and closed.

  verify_no_orphan_workloads.py                       # live scan of DEFAULT_NAMESPACES (below)
  verify_no_orphan_workloads.py --namespace scm        # scan one namespace only
  verify_no_orphan_workloads.py --namespace a,b,c      # scan an explicit comma-separated list
  verify_no_orphan_workloads.py --self-test            # prove the classifier discriminates
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# Every prod namespace this detector is responsible for. Adding a namespace here is how you close
# a blind spot like the one that hid scm/gitea for 20 days — do this whenever a new namespace gets
# a workload that isn't Helm/ArgoCD-managed from day one.
DEFAULT_NAMESPACES: tuple[str, ...] = ("socioprophet", "scm")

# Workloads intentionally applied outside ArgoCD (via a CI workflow's kubectl apply), TODAY.
# Each SHOULD graduate to an ArgoCD Application; until then it is allowlisted so the gate does not
# cry wolf. Shrink-only: do not add to this — a new out-of-band workload is meant to fail.
# Keys are "<namespace>/<name>" — see the module docstring for why bare names are unsafe here.
SANCTIONED_OUT_OF_BAND: frozenset[str] = frozenset({
    "socioprophet/gitea",            # sovereign git server (empty instance) — deploy-gitea-authority.yml (workflow apply)
    "socioprophet/gitea-authority",  # sovereign token authority — same workflow
    "scm/gitea",                     # THE real sovereign SCM (code.socioprophet.ai, 125 repos) — brought under
                                      # ArgoCD by deploy/argocd/gitea-scm-sovereign.yaml in this same change; kept
                                      # sanctioned only until that Application is confirmed synced (mirrors the
                                      # socioprophet/* entries' own disposition) — remove once verified GitOps-managed.
})


def is_gitops_managed(deploy: dict) -> bool:
    """True if a workload is continuously reconciled (ArgoCD) or Helm-managed."""
    meta = deploy.get("metadata") or {}
    ann = meta.get("annotations") or {}
    lbl = meta.get("labels") or {}
    return ("argocd.argoproj.io/tracking-id" in ann
            or bool(lbl.get("argocd.argoproj.io/instance"))
            or lbl.get("app.kubernetes.io/managed-by") == "Helm")


def _qualified_name(deploy: dict) -> str:
    """'<namespace>/<name>' — the allowlist key. Falls back to '?' for malformed input."""
    meta = deploy.get("metadata") or {}
    return f"{meta.get('namespace', '?')}/{meta.get('name', '?')}"


def find_problems(deployments: list[dict], allowlist: frozenset[str]) -> list[str]:
    """Ratchet: a NEW out-of-band workload OR a stale allowlist entry → a problem."""
    problems: list[str] = []
    present = {_qualified_name(d): d for d in deployments}
    orphans = {n for n, d in present.items() if not is_gitops_managed(d)}
    for name in sorted(orphans - allowlist):
        problems.append(f"ORPHAN workload (out-of-band; not ArgoCD/Helm-managed, not sanctioned): "
                        f"{name} — bring it under an ArgoCD Application, or it will rot unseen")
    for name in sorted(allowlist):
        d = present.get(name)
        if d is not None and is_gitops_managed(d):
            problems.append(f"STALE allowlist entry: {name} is now GitOps-managed — remove it from "
                            f"SANCTIONED_OUT_OF_BAND (the ratchet only shrinks)")
    return problems


def collect_deployments(namespace: str) -> list[dict] | None:
    ctx = os.environ.get("KUBE_CONTEXT")   # honor an explicit context (concurrent-agent hazard)
    cmd = ["kubectl"] + (["--context", ctx] if ctx else []) + ["-n", namespace, "get", "deploy", "-o", "json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        sys.stderr.write(f"[orphan-check] {' '.join(cmd)} rc={r.returncode}: {r.stderr.strip()[:200]}\n")
        return None
    try:
        return json.loads(r.stdout).get("items", [])
    except json.JSONDecodeError:
        return None


def _self_test() -> bool:
    argocd = {"metadata": {"namespace": "ns", "name": "a", "annotations": {"argocd.argoproj.io/tracking-id": "x"}}}
    helm = {"metadata": {"namespace": "ns", "name": "h", "labels": {"app.kubernetes.io/managed-by": "Helm"}}}
    orphan = {"metadata": {"namespace": "ns", "name": "evil", "labels": {"app": "evil"}}}
    sanctioned = {"metadata": {"namespace": "ns", "name": "gitea", "labels": {"app": "gitea"}}}
    same_name_other_ns = {"metadata": {"namespace": "other-ns", "name": "gitea", "labels": {"app": "gitea"}}}
    checks = [
        ("argocd-managed is not an orphan", is_gitops_managed(argocd) is True),
        ("helm-managed is not an orphan", is_gitops_managed(helm) is True),
        ("bare workload is an orphan", is_gitops_managed(orphan) is False),
        ("new out-of-band workload FAILS the gate",
         find_problems([orphan], frozenset({"ns/gitea"})) != []),
        ("sanctioned out-of-band workload passes",
         find_problems([sanctioned], frozenset({"ns/gitea"})) == []),
        ("same bare name in an UNsanctioned namespace still FAILS "
         "(namespace-qualified, not bare-name, matching)",
         find_problems([same_name_other_ns], frozenset({"ns/gitea"})) != []),
        ("sanctioned-but-now-managed is flagged STALE",
         any("STALE" in p for p in find_problems(
             [{"metadata": {"namespace": "ns", "name": "gitea",
                            "annotations": {"argocd.argoproj.io/tracking-id": "x"}}}],
             frozenset({"ns/gitea"})))),
    ]
    ok = all(v for _, v in checks)
    for name, v in checks:
        print(f"    {'OK  ' if v else 'FAIL'} self-test: {name}")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Detect out-of-band (non-GitOps) prod workloads.")
    ap.add_argument("--namespace", default=",".join(DEFAULT_NAMESPACES),
                     help="comma-separated list of namespaces to scan")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if not _self_test():
        print("FAIL: self-test did not pass — the orphan detector has no teeth")
        return 2
    if args.self_test:
        return 0
    namespaces = [ns.strip() for ns in args.namespace.split(",") if ns.strip()]
    deployments: list[dict] = []
    for ns in namespaces:
        found = collect_deployments(ns)
        if found is None:
            print(f"FAIL: could not list deployments in {ns} (no access / wrong context) — "
                  f"absence of observed orphans is not evidence of none")
            return 2
        deployments.extend(found)
    problems = find_problems(deployments, SANCTIONED_OUT_OF_BAND)
    scanned = ", ".join(namespaces)
    if problems:
        print(f"FAIL: {len(problems)} out-of-band workload problem(s) across [{scanned}]:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"OK: every workload in [{scanned}] is GitOps-managed or a shrinking sanctioned "
          f"entry ({len(SANCTIONED_OUT_OF_BAND)} sanctioned: {', '.join(sorted(SANCTIONED_OUT_OF_BAND))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
