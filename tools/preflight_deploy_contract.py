#!/usr/bin/env python3
"""Preflight: every deployed service must reference something that exists.

CI builds images. Nothing checked that the things we DEPLOY line up with the
things we BUILD — so on 2026-07-15 the cluster had ~9 pods crashlooping for two
days behind a 100% green pipeline. Every one of those failures passed CI.

Two checks, both static (no registry credentials, runs anywhere):

  1. Every service in a deploy/argocd ApplicationSet has a deploy/values/<name>.yaml.
  2. Every FIRST-PARTY service is actually built by .github/workflows/images.yml.

First-party vs third-party is decided by image.registry: third-party values pin a
foreign registry explicitly (socbase-auth -> docker.io/supabase/gotrue), while
first-party values omit it and inherit the platform default from the chart. So a
values file with no registry override is claiming "the platform builds this" —
and this asserts that claim is true.

Caught in the wild: reasoning-failure-runner is deployed, is first-party, has zero
entries in images.yml, and its image has never existed in GAR. It ImagePullBackOffs
forever. Same class as workspace-{mail,caldav,smtp}, which CI built to GAR while
the deployments pulled from GHCR — a registry they were never published to.

Exit 0 = clean, 1 = a deployment references something that will never resolve.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    print("preflight: PyYAML required (pip install pyyaml)", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
ARGOCD_DIR = ROOT / "deploy" / "argocd"
VALUES_DIR = ROOT / "deploy" / "values"
IMAGES_WF = ROOT / ".github" / "workflows" / "images.yml"

# Services deployed from their own kustomize base under infra/k8s/<name>/ rather
# than the shared chart + deploy/values. They skip the values checks but are still
# checked, via their kustomize manifests, by check_kustomize_images().
NON_CHART_SERVICES = {
    "zot",
    "workspace-minio",
    "workspace-mail",
    "workspace-caldav",
    "workspace-smtp",
}

# Registry hosts this platform actually publishes to. An image ref pointing anywhere
# else is either third-party (fine) or a mistake (workspace-* pointed at GHCR, which
# CI has never published to — so the pods could only ever ImagePullBackOff).
OUR_REGISTRIES = ("us-central1-docker.pkg.dev/socioprophet-platform/", "registry.socioprophet.ai/")

# Ratchet: known-broken services, reported but not failing the build. This exists so
# the gate can be enforced TODAY — blocking every NEW violation — without waiting on
# pre-existing debt whose fix is a product decision rather than a config change.
# Entries must carry a reason. The list should only ever shrink.
KNOWN_BROKEN = {
    "reasoning-failure-runner": (
        "apps/reasoning-failure-runner has src/ and examples/ but NO Dockerfile, so no "
        "image can exist — yet platform-services.yaml deploys it, giving a permanent "
        "ImagePullBackOff. It looks like a library that was added to the ApplicationSet "
        "as if it were a service. Fix = add a Dockerfile + images.yml entry, or drop it "
        "from the ApplicationSet. Needs an owner decision, not a config tweak."
    ),
}

# Registries that are explicitly not ours. A values file naming one of these is
# declaring "third party, we don't build it" — which is a legitimate answer.
FOREIGN_REGISTRY_RE = re.compile(r"^(docker\.io|ghcr\.io|quay\.io|registry\.k8s\.io|gcr\.io/(?!socioprophet))")


def deployed_services() -> set[str]:
    """Service names from every ApplicationSet list generator under deploy/argocd."""
    names: set[str] = set()
    for path in sorted(ARGOCD_DIR.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        # Parse loosely: these files are Go-templated, so yaml.safe_load can choke.
        names |= set(re.findall(r"^\s*-\s*\{\s*name:\s*([a-z0-9][a-z0-9-]*)", text, re.M))
    return names


def built_images() -> set[str]:
    """Image names from the images.yml build matrix."""
    if not IMAGES_WF.exists():
        return set()
    text = IMAGES_WF.read_text(encoding="utf-8")
    return set(re.findall(r"^\s*-\s*\{\s*image:\s*([a-z0-9][a-z0-9-]*)\s*,", text, re.M))


def check_kustomize_images(name: str, built: set[str]) -> list[str]:
    """Image refs in a kustomize-deployed service must point at a registry we publish to.

    workspace-{mail,caldav,smtp} referenced ghcr.io/socioprophet/prophet-platform/*
    while images.yml built them to Artifact Registry. The images were never in GHCR
    at all, so no pull secret could have helped — the ref was simply wrong.
    """
    base = ROOT / "infra" / "k8s" / name
    if not base.exists():
        # Some kustomize services live under a sibling's tree (workspace-smtp is
        # defined inside infra/k8s/workspace-mail/). Nothing to assert here.
        return []
    problems: list[str] = []
    for manifest in sorted(base.rglob("*.yaml")):
        text = manifest.read_text(encoding="utf-8")
        # `image: <ref>` in a manifest, AND `value: <ref>` inside a kustomize JSON
        # patch that replaces .../containers/N/image. The patch form is what bit us:
        # the base was repointed to zot while overlays/p0-lab silently patched the
        # image back to GHCR, so the deployed pod never moved and the first version
        # of this gate — which only looked for `image:` — passed anyway.
        refs = re.findall(r"^\s*image:\s*(\S+)", text, re.M)
        refs += re.findall(r"path:\s*\S*/image\s*\n\s*value:\s*(\S+)", text)
        for ref in refs:
            ref = ref.strip("\"'")
            if FOREIGN_REGISTRY_RE.match(ref) and not ref.startswith("ghcr.io/socioprophet"):
                continue  # genuine third-party upstream image
            if ref.startswith(OUR_REGISTRIES):
                continue  # points at a registry we publish to
            repo = ref.split("/")[-1].split(":")[0]
            if repo in built:
                problems.append(
                    f"{name}: {manifest.relative_to(ROOT)} pulls '{ref}' but CI builds "
                    f"'{repo}' to {OUR_REGISTRIES[0]}… — the pods pull from a registry "
                    f"the image was never published to."
                )
    return problems


def main() -> int:
    services = deployed_services()
    built = built_images()
    if not services:
        print("preflight: found no deployed services — check deploy/argocd/", file=sys.stderr)
        return 1

    problems: list[str] = []
    checked = 0

    for name in sorted(services):
        if name in NON_CHART_SERVICES:
            problems.extend(check_kustomize_images(name, built))
            continue
        values_path = VALUES_DIR / f"{name}.yaml"
        if not values_path.exists():
            problems.append(f"{name}: deployed by an ApplicationSet but deploy/values/{name}.yaml is missing")
            continue

        data = yaml.safe_load(values_path.read_text(encoding="utf-8")) or {}
        image = data.get("image") or {}
        repository = image.get("repository")
        registry = (image.get("registry") or "").strip()

        if not repository:
            problems.append(f"{name}: values has no image.repository")
            continue

        if registry and FOREIGN_REGISTRY_RE.match(registry):
            continue  # third-party, we don't build it — legitimately out of scope

        checked += 1
        if repository not in built:
            problems.append(
                f"{name}: first-party image '{repository}' has NO entry in images.yml — "
                f"it is deployed but never built, so it can only ImagePullBackOff. "
                f"Add it to the build matrix, pin a foreign image.registry if it is "
                f"third-party, or remove the service from the ApplicationSet."
            )

    # Split real failures from ratcheted, already-known debt.
    blocking = [p for p in problems if p.split(":")[0] not in KNOWN_BROKEN]
    known = [p for p in problems if p.split(":")[0] in KNOWN_BROKEN]

    print(f"preflight: {len(services)} deployed, {checked} first-party checked against {len(built)} built images")

    if known:
        print("\nKNOWN BROKEN (ratcheted — tracked, not blocking):")
        for p in known:
            name = p.split(":")[0]
            print(f"  • {p}")
            print(f"      why deferred: {KNOWN_BROKEN[name]}")

    stale = sorted(set(KNOWN_BROKEN) - {p.split(":")[0] for p in problems})
    if stale:
        print("\nFAIL — these are in KNOWN_BROKEN but now pass. The ratchet only shrinks:", file=sys.stderr)
        for name in stale:
            print(f"  • {name}: fixed — delete it from KNOWN_BROKEN", file=sys.stderr)
        return 1

    if blocking:
        print("\nFAIL — a deployment references something that will never resolve:\n", file=sys.stderr)
        for p in blocking:
            print(f"  • {p}", file=sys.stderr)
        return 1

    print("OK: every deployed first-party service is built by CI and pulls from a registry we publish to")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
