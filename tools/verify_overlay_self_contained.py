#!/usr/bin/env python3
"""Preflight (INV-DEP-10): every workload pod-template ref must resolve in the overlay it deploys.

A Deployment or Argo Rollouts `Rollout` names the supporting objects its pods need — a
`serviceAccountName`, `configMapRef`/`configMap` volume, `persistentVolumeClaim.claimName`. Those
names are resolved by the Kubernetes API at pod-CREATE time against the workload's OWN namespace.
An overlay that renders the workload but NOT the object it names produces YAML that
`kubectl kustomize` prints perfectly and the live cluster rejects the moment it tries to schedule:

    FailedCreate: pods "search-orchestrator-..." is forbidden: error looking up service account
    prophet-platform-prod/search-orchestrator: serviceaccount "search-orchestrator" not found
        (ReplicaSet ReplicaFailure, 0 pods, Rollout stuck Progressing)

That is exactly what the 2026-08-02 wave-deploy hit: the prod blue-green overlay was authored as
a Rollout + Service and commented "Self-contained", but it never rendered the ServiceAccount,
ConfigMap, or PVC that the Rollout's pod template referenced (those lived in `base`, and the
overlay could not list files above its own dir). Dry-run kustomize was green; the real apply to a
fresh `prophet-platform-prod` namespace created zero pods. This gate makes an overlay prove it is
genuinely self-contained: every SA / ConfigMap / PVC a workload names is rendered by the SAME
overlay — so a single `kustomize build | kubectl apply` (one-click) stands the whole thing up.

Teeth both ways: tools/tests/test_verify_overlay_self_contained.py feeds a resolvable overlay
(passes) and a workload whose serviceAccountName / configMap / PVC is not rendered (fails). A gate
that has only ever passed proves nothing.

Runs static (no cluster): it shells out to `kubectl kustomize` to render each overlay, then
inspects the rendered YAML. Wired into `make overlay-self-contained-check` (the
validate-target-diagnostics matrix) and `wave-promote.yml`, alongside INV-DEP-9.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]

WORKLOAD_KINDS = {"Deployment", "Rollout", "StatefulSet", "DaemonSet"}

# The wave overlays this gate renders by default. Each must render every supporting object its
# workload pod template references.
DEFAULT_OVERLAYS = [
    "infra/k8s/search-orchestrator/overlays/promote/dev",
    "infra/k8s/search-orchestrator/overlays/promote/canary",
    "infra/k8s/search-orchestrator/overlays/promote/prod",
]

# The default ServiceAccount always exists in every namespace; a workload that names it needs no
# rendered SA. Any other name must be rendered by the overlay.
_IMPLICIT_SA = {"default", ""}


def _load_docs(text: str) -> tuple[list[dict[str, Any]], str | None]:
    """Parse every YAML doc. Fail-closed: a parse error is surfaced, never swallowed — a
    manifest that will not parse cannot be certified self-contained."""
    try:
        return [d for d in yaml.safe_load_all(text) if isinstance(d, dict)], None
    except yaml.YAMLError as e:
        return [], type(e).__name__


def _pod_spec(doc: dict[str, Any]) -> dict[str, Any]:
    """The pod spec inside a workload (Deployment/Rollout/StatefulSet/DaemonSet share the shape:
    spec.template.spec)."""
    tmpl = ((doc.get("spec") or {}).get("template") or {})
    return tmpl.get("spec") or {}


def _containers(pod: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("initContainers", "containers", "ephemeralContainers"):
        for c in pod.get(key) or []:
            if isinstance(c, dict):
                yield c


def workload_refs(doc: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    """(serviceAccounts, configMaps, pvcClaims) a workload's pod template references."""
    pod = _pod_spec(doc)
    sas: set[str] = set()
    cms: set[str] = set()
    pvcs: set[str] = set()

    sa = pod.get("serviceAccountName") or pod.get("serviceAccount")
    if sa is not None:
        sas.add(str(sa))

    # configMap / PVC references carried by volumes
    for vol in pod.get("volumes") or []:
        if not isinstance(vol, dict):
            continue
        cm = vol.get("configMap")
        if isinstance(cm, dict) and cm.get("name"):
            cms.add(str(cm["name"]))
        pvc = vol.get("persistentVolumeClaim")
        if isinstance(pvc, dict) and pvc.get("claimName"):
            pvcs.add(str(pvc["claimName"]))
        proj = vol.get("projected")
        if isinstance(proj, dict):
            for src in proj.get("sources") or []:
                if isinstance(src, dict) and isinstance(src.get("configMap"), dict) and src["configMap"].get("name"):
                    cms.add(str(src["configMap"]["name"]))

    # configMap references carried by containers (envFrom / env valueFrom)
    for c in _containers(pod):
        for ef in c.get("envFrom") or []:
            if isinstance(ef, dict) and isinstance(ef.get("configMapRef"), dict) and ef["configMapRef"].get("name"):
                cms.add(str(ef["configMapRef"]["name"]))
        for e in c.get("env") or []:
            if not isinstance(e, dict):
                continue
            vf = e.get("valueFrom")
            if isinstance(vf, dict) and isinstance(vf.get("configMapKeyRef"), dict) and vf["configMapKeyRef"].get("name"):
                cms.add(str(vf["configMapKeyRef"]["name"]))

    return sas, cms, pvcs


def rendered_names(docs: list[dict[str, Any]], kind: str) -> set[str]:
    out: set[str] = set()
    for d in docs:
        if d.get("kind") == kind:
            name = (d.get("metadata") or {}).get("name")
            if name:
                out.add(str(name))
    return out


def ref_violations(docs: list[dict[str, Any]], where: str) -> list[str]:
    """Every SA/ConfigMap/PVC a workload names must be rendered in the SAME doc set."""
    sas = rendered_names(docs, "ServiceAccount")
    cms = rendered_names(docs, "ConfigMap")
    pvcs = rendered_names(docs, "PersistentVolumeClaim")
    out: list[str] = []
    for d in docs:
        if d.get("kind") not in WORKLOAD_KINDS:
            continue
        wname = (d.get("metadata") or {}).get("name", "<unnamed>")
        kind = d.get("kind")
        ref_sas, ref_cms, ref_pvcs = workload_refs(d)
        for sa in ref_sas - _IMPLICIT_SA:
            if sa not in sas:
                out.append(
                    f"{where}: {kind} '{wname}' sets serviceAccountName '{sa}', but this overlay "
                    f"does not render a ServiceAccount '{sa}' — an apply to a fresh namespace "
                    f"FailedCreate's 'serviceaccount {sa!r} not found' (0 pods). Render the SA "
                    f"in this overlay (e.g. add base-support to resources)."
                )
        for cm in ref_cms:
            if cm not in cms:
                out.append(
                    f"{where}: {kind} '{wname}' references ConfigMap '{cm}', but this overlay does "
                    f"not render it — pods stay ContainerCreating "
                    f"('configmap {cm!r} not found'). Render the ConfigMap in this overlay."
                )
        for pvc in ref_pvcs:
            if pvc not in pvcs:
                out.append(
                    f"{where}: {kind} '{wname}' mounts PVC claimName '{pvc}', but this overlay does "
                    f"not render a PersistentVolumeClaim '{pvc}' — pods stay Pending "
                    f"('persistentvolumeclaim {pvc!r} not found'). Render the PVC in this overlay."
                )
    return out


def scan_rendered(text: str, where: str = "<rendered>") -> list[str]:
    """Parse rendered multi-doc YAML and return self-containment violations. The test seam."""
    docs, err = _load_docs(text)
    if err is not None:
        return [f"{where}: rendered output is not valid YAML ({err}); cannot certify self-contained"]
    return ref_violations(docs, where)


def render_overlay(overlay: Path) -> tuple[str, str | None]:
    """Render an overlay via `kubectl kustomize`. A non-zero exit is a fail-closed error."""
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
        violations.extend(scan_rendered(text, where=rel))
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
        print("Overlay self-containment check FAILED (INV-DEP-10):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print(f"OK: {len(overlays)} overlay(s) render every SA/ConfigMap/PVC their workloads reference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
