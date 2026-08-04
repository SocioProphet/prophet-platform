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

  verify_no_orphan_workloads.py --namespace socioprophet   # live scan (kubectl --context aware)
  verify_no_orphan_workloads.py --self-test                # prove the classifier discriminates
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# Workloads intentionally applied outside ArgoCD (via a CI workflow's kubectl apply), TODAY.
# Each SHOULD graduate to an ArgoCD Application; until then it is allowlisted so the gate does not
# cry wolf. Shrink-only: do not add to this — a new out-of-band workload is meant to fail.
SANCTIONED_OUT_OF_BAND: frozenset[str] = frozenset({
    "gitea",            # sovereign git server — deployed by deploy-gitea-authority.yml (workflow apply)
    "gitea-authority",  # sovereign token authority — same workflow
})


def is_gitops_managed(deploy: dict) -> bool:
    """True if a workload is continuously reconciled (ArgoCD) or Helm-managed."""
    meta = deploy.get("metadata") or {}
    ann = meta.get("annotations") or {}
    lbl = meta.get("labels") or {}
    return ("argocd.argoproj.io/tracking-id" in ann
            or bool(lbl.get("argocd.argoproj.io/instance"))
            or lbl.get("app.kubernetes.io/managed-by") == "Helm")


def find_problems(deployments: list[dict], allowlist: frozenset[str]) -> list[str]:
    """Ratchet: a NEW out-of-band workload OR a stale allowlist entry → a problem."""
    problems: list[str] = []
    present = {(d.get("metadata") or {}).get("name", "?"): d for d in deployments}
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
    argocd = {"metadata": {"name": "a", "annotations": {"argocd.argoproj.io/tracking-id": "x"}}}
    helm = {"metadata": {"name": "h", "labels": {"app.kubernetes.io/managed-by": "Helm"}}}
    orphan = {"metadata": {"name": "evil", "labels": {"app": "evil"}}}
    sanctioned = {"metadata": {"name": "gitea", "labels": {"app": "gitea"}}}
    checks = [
        ("argocd-managed is not an orphan", is_gitops_managed(argocd) is True),
        ("helm-managed is not an orphan", is_gitops_managed(helm) is True),
        ("bare workload is an orphan", is_gitops_managed(orphan) is False),
        ("new out-of-band workload FAILS the gate",
         find_problems([orphan], SANCTIONED_OUT_OF_BAND) != []),
        ("sanctioned out-of-band workload passes",
         find_problems([sanctioned], SANCTIONED_OUT_OF_BAND) == []),
        ("sanctioned-but-now-managed is flagged STALE",
         any("STALE" in p for p in find_problems(
             [{"metadata": {"name": "gitea", "annotations": {"argocd.argoproj.io/tracking-id": "x"}}}],
             SANCTIONED_OUT_OF_BAND))),
    ]
    ok = all(v for _, v in checks)
    for name, v in checks:
        print(f"    {'OK  ' if v else 'FAIL'} self-test: {name}")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Detect out-of-band (non-GitOps) prod workloads.")
    ap.add_argument("--namespace", default="socioprophet")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if not _self_test():
        print("FAIL: self-test did not pass — the orphan detector has no teeth")
        return 2
    if args.self_test:
        return 0
    deployments = collect_deployments(args.namespace)
    if deployments is None:
        print(f"FAIL: could not list deployments in {args.namespace} (no access / wrong context) — "
              f"absence of observed orphans is not evidence of none")
        return 2
    problems = find_problems(deployments, SANCTIONED_OUT_OF_BAND)
    if problems:
        print(f"FAIL: {len(problems)} out-of-band workload problem(s) in {args.namespace}:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"OK: every workload in {args.namespace} is GitOps-managed or a shrinking sanctioned "
          f"entry ({len(SANCTIONED_OUT_OF_BAND)} sanctioned: {', '.join(sorted(SANCTIONED_OUT_OF_BAND))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
