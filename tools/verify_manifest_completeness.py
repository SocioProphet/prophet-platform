#!/usr/bin/env python3
"""Preflight (INV-DEP-11): DERIVED reference completeness for every promote overlay.

INV-DEP-9 (verify_rollout_analysis_refs.py) resolves Rollout analysis-template refs and INV-DEP-10
(verify_overlay_self_contained.py) resolves ServiceAccount / ConfigMap / PVC refs. Each of those is
a POINT gate: someone read a live incident, named the one reference type that bit us, and hand-wrote
a checker for it. That leaves a standing hole — the NEXT reference type a workload can name (a
Secret, a floating image tag) reaches prod uncaught until a fresh incident teaches us to write the
next point gate. This gate closes that hole for the reference classes 9/10 do not cover, so a novel
ref type cannot ride to a fresh namespace and fail at create/spec time before anyone notices:

    Warning  FailedMount  pod/search-orchestrator-...  secret "search-orchestrator-tls" not found
    Warning  Failed       pod/search-orchestrator-...  Error: ErrImagePull (manifest unknown)

Like 9/10 it renders each promote overlay with `kubectl kustomize` (dry-run green) and then proves
the rendered set is COMPLETE, deny-closed, one specific reason per miss:

  * SECRET refs — for every workload (Deployment/Rollout/StatefulSet/DaemonSet) it derives every
    Secret the pod template names (volumes[].secret.secretName; envFrom[].secretRef.name;
    env[].valueFrom.secretKeyRef.name; volumes[].projected.sources[].secret.name;
    imagePullSecrets[].name) and requires each to be rendered in the SAME set OR listed in
    infra/k8s/search-orchestrator/external-secrets.allowlist.yaml (externally provisioned — e.g. by
    the External Secrets operator — with a documented reason). A ref that is neither rendered nor
    allowlisted FailedMount's / FailedCreate's on a real apply, so it fails here.

  * IMAGE digest-pinning — every container image (initContainers + containers) MUST be pinned to a
    real `@sha256:<64 hex>` digest (INV-DEP-1/2, build-once-promote-many). A floating tag is
    repointed under you between render and pull; a placeholder digest (contains REPLACE/PLACEHOLDER,
    is all-zeros, or is not 64 lowercase hex) never resolves to an image (ImagePullBackOff). Either
    fails here.

It deliberately does NOT re-implement SA/ConfigMap/PVC (INV-DEP-10) or analysis-template
(INV-DEP-9) resolution — those two are its siblings; run all three. Together they make the promote
overlays prove, statically, that a single `kustomize build | kubectl apply` resolves every reference
the live cluster checks at pod-create / spec-admission time.

Teeth both ways: tools/tests/test_verify_manifest_completeness.py feeds shipped overlays (pass), a
dangling secretRef, a floating-tag image, a placeholder digest (each fails), and malformed YAML
(fail-closed). A gate that has only ever passed proves nothing.

Runs static (no cluster): shells out to `kubectl kustomize`, then inspects the rendered YAML. Wired
into `make manifest-completeness-check` (the validate-target-diagnostics matrix), alongside
INV-DEP-9/10. The complementary L1 gate (.github/workflows/ephemeral-apply-preflight.yml) then
actually applies each overlay to a throwaway kind namespace and asserts the same failure class does
not occur live — static derivation here, real apply there.
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

# The wave overlays this gate renders by default — the SAME set INV-DEP-9/10 render. Each must
# render (or allowlist) every Secret its workloads name and pin every image to a real digest.
# NOTE: the negative fixture overlays/_selftest-broken is deliberately NOT in this list — it exists
# to prove the L1 real-apply detector can fail, and must never be certified by 9/10/11.
DEFAULT_OVERLAYS = [
    "infra/k8s/search-orchestrator/overlays/promote/dev",
    "infra/k8s/search-orchestrator/overlays/promote/canary",
    "infra/k8s/search-orchestrator/overlays/promote/prod",
]

# Externally-provisioned Secrets a workload may reference without the overlay rendering them (the
# External Secrets operator / a bootstrap job materialises them). Each entry is documented + reasoned
# in the file; an unlisted, unrendered Secret ref fails.
EXTERNAL_SECRETS_ALLOWLIST = "infra/k8s/search-orchestrator/external-secrets.allowlist.yaml"

_HEX = set("0123456789abcdef")


def _load_docs(text: str) -> tuple[list[dict[str, Any]], str | None]:
    """Parse every YAML doc. Fail-closed: a parse error is surfaced, never swallowed — a
    manifest that will not parse cannot be certified complete."""
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
    """Every image-bearing / secret-referencing container: initContainers + containers (and
    ephemeralContainers, a strict superset — being broader is deny-closed)."""
    for key in ("initContainers", "containers", "ephemeralContainers"):
        for c in pod.get(key) or []:
            if isinstance(c, dict):
                yield c


def workload_secret_refs(doc: dict[str, Any]) -> set[str]:
    """Every Secret name a workload's pod template references — the classes INV-DEP-10 does NOT
    cover: secret volumes, envFrom.secretRef, env.valueFrom.secretKeyRef, projected secret sources,
    and imagePullSecrets."""
    pod = _pod_spec(doc)
    secrets: set[str] = set()

    for vol in pod.get("volumes") or []:
        if not isinstance(vol, dict):
            continue
        sec = vol.get("secret")
        if isinstance(sec, dict) and sec.get("secretName"):
            secrets.add(str(sec["secretName"]))
        proj = vol.get("projected")
        if isinstance(proj, dict):
            for src in proj.get("sources") or []:
                if isinstance(src, dict) and isinstance(src.get("secret"), dict) and src["secret"].get("name"):
                    secrets.add(str(src["secret"]["name"]))

    for c in _containers(pod):
        for ef in c.get("envFrom") or []:
            if isinstance(ef, dict) and isinstance(ef.get("secretRef"), dict) and ef["secretRef"].get("name"):
                secrets.add(str(ef["secretRef"]["name"]))
        for e in c.get("env") or []:
            if not isinstance(e, dict):
                continue
            vf = e.get("valueFrom")
            if isinstance(vf, dict) and isinstance(vf.get("secretKeyRef"), dict) and vf["secretKeyRef"].get("name"):
                secrets.add(str(vf["secretKeyRef"]["name"]))

    for ips in pod.get("imagePullSecrets") or []:
        if isinstance(ips, dict) and ips.get("name"):
            secrets.add(str(ips["name"]))

    return secrets


def workload_images(doc: dict[str, Any]) -> list[tuple[str, str]]:
    """(containerName, image) for every image-bearing container in a workload."""
    out: list[tuple[str, str]] = []
    for c in _containers(_pod_spec(doc)):
        image = c.get("image")
        if image is not None:
            out.append((str(c.get("name", "<unnamed>")), str(image)))
    return out


def image_digest_problem(image: str) -> str | None:
    """Return a human reason `image` is not pinned to a REAL sha256 digest, or None if it is.

    Deny-closed: a floating tag, a placeholder digest (REPLACE/PLACEHOLDER text, all-zeros, or a
    digest that is not exactly 64 lowercase hex chars) all fail — only a genuine 64-hex digest
    resolves to an immutable image."""
    if "@sha256:" not in image:
        return (
            "is not digest-pinned (no '@sha256:' digest) — a floating tag is repointed under you "
            "between render and pull; pin it to a sha256 digest (INV-DEP-1/2, build-once-promote-"
            "many)"
        )
    if "REPLACE" in image.upper() or "PLACEHOLDER" in image.upper():
        return (
            "carries a PLACEHOLDER digest (contains REPLACE/PLACEHOLDER) — the promotion never "
            "stamped the frozen digest; this pulls nothing (ImagePullBackOff)"
        )
    digest = image.partition("@sha256:")[2]
    if len(digest) != 64 or any(c not in _HEX for c in digest):
        return (
            f"has a malformed sha256 digest {digest!r} — a real digest is exactly 64 lowercase hex "
            f"chars; a truncated/hand-typed digest never resolves to an image"
        )
    if digest == "0" * 64:
        return (
            "has an all-zeros sha256 digest (a placeholder), never a real image "
            "(ImagePullBackOff)"
        )
    return None


def rendered_names(docs: list[dict[str, Any]], kind: str) -> set[str]:
    out: set[str] = set()
    for d in docs:
        if d.get("kind") == kind:
            name = (d.get("metadata") or {}).get("name")
            if name:
                out.add(str(name))
    return out


def ref_violations(
    docs: list[dict[str, Any]],
    allowed_external_secrets: set[str],
    where: str,
) -> list[str]:
    """Every Secret a workload names must be rendered in the SAME set or allowlisted; every image
    must be pinned to a real digest."""
    rendered_secrets = rendered_names(docs, "Secret")
    resolvable_secrets = rendered_secrets | allowed_external_secrets
    out: list[str] = []
    for d in docs:
        if d.get("kind") not in WORKLOAD_KINDS:
            continue
        wname = (d.get("metadata") or {}).get("name", "<unnamed>")
        kind = d.get("kind")
        for sec in sorted(workload_secret_refs(d)):
            if sec not in resolvable_secrets:
                out.append(
                    f"{where}: {kind} '{wname}' references Secret '{sec}', but this overlay does "
                    f"not render it and it is not in {EXTERNAL_SECRETS_ALLOWLIST} — a real apply "
                    f"FailedMount's / FailedCreate's ('secret {sec!r} not found'). Render the "
                    f"Secret in this overlay, or add '{sec}' to the external-secrets allowlist with "
                    f"a documented provisioner."
                )
        for cname, image in workload_images(d):
            problem = image_digest_problem(image)
            if problem is not None:
                out.append(
                    f"{where}: {kind} '{wname}' container '{cname}' image {image!r} {problem}."
                )
    return out


def scan_rendered(
    text: str,
    allowed_external_secrets: set[str] | None = None,
    where: str = "<rendered>",
) -> list[str]:
    """Parse rendered multi-doc YAML and return completeness violations. The test seam."""
    docs, err = _load_docs(text)
    if err is not None:
        return [f"{where}: rendered output is not valid YAML ({err}); cannot certify complete"]
    return ref_violations(docs, allowed_external_secrets or set(), where)


def load_external_secret_allowlist(root: Path) -> tuple[set[str], str | None]:
    """Names of externally-provisioned Secrets a workload may reference without the overlay
    rendering them. Absent file == nothing allowlisted (deny-closed). A malformed allowlist is a
    fail-closed error, never silently treated as empty (that would launder every dangling ref)."""
    path = root / EXTERNAL_SECRETS_ALLOWLIST
    if not path.exists():
        return set(), None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return set(), f"{EXTERNAL_SECRETS_ALLOWLIST}: cannot read ({type(e).__name__})"
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return set(), f"{EXTERNAL_SECRETS_ALLOWLIST}: not valid YAML ({type(e).__name__})"
    if doc is None:
        return set(), None
    if not isinstance(doc, dict):
        return set(), f"{EXTERNAL_SECRETS_ALLOWLIST}: expected a mapping with 'externalSecrets:'"
    names: set[str] = set()
    for entry in doc.get("externalSecrets") or []:
        if isinstance(entry, dict) and entry.get("name"):
            names.add(str(entry["name"]))
    return names, None


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
    allowed, alerr = load_external_secret_allowlist(root)
    if alerr is not None:
        return [alerr]
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
        violations.extend(scan_rendered(text, allowed, where=rel))
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
        print("Manifest completeness check FAILED (INV-DEP-11):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    allowed, _ = load_external_secret_allowlist(ROOT)
    print(
        f"OK: {len(overlays)} overlay(s) render every Secret their workloads reference "
        f"(allowlisted external: {sorted(allowed) or 'none'}) and pin every image to a digest."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
