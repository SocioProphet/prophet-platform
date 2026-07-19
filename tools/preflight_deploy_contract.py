#!/usr/bin/env python3
"""Preflight: every deployed service must reference something that exists.

CI builds images. Nothing checked that the things we DEPLOY line up with the
things we BUILD — so on 2026-07-15 the cluster had ~9 pods crashlooping for two
days behind a 100% green pipeline. Every one of those failures passed CI.

Four checks, all static (no registry credentials, runs anywhere):

  1. Every service in a deploy/argocd ApplicationSet has a deploy/values/<name>.yaml.
  2. Every FIRST-PARTY service is actually built by .github/workflows/images.yml.
  3. No service deploys a MOVING tag (`latest`). The chart already states the rule —
     "Immutable tag = the commit SHA the GitOps promotion writes" — but a comment is
     a conclusion, not a gate. `latest` + imagePullPolicy: IfNotPresent means kubelet
     reuses the node cache forever: a fixed image never rolls out, and `rollout
     restart` does not re-pull. That is how a broken socioprophet-web build survived
     574 restarts while `latest` in the registry was already fixed.
  4. Every FIRST-PARTY service PINS a tag. An omitted image.tag is not `latest` — it
     inherits the chart's appVersion default, which the build never publishes, so the
     pod ImagePullBackOffs on a tag that does not exist. This slipped past check 3
     ("" is not a moving tag) and cost dashboard-bff 108 minutes (#743).

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
    "searxng",   # sovereign meta-search, deploys from infra/k8s/searxng (kustomize)
    "commons-search",  # open-chat commons aggregator, deploys from infra/k8s/commons-search (kustomize)
    "search-gateway-ingress",  # public HTTPS edge (ManagedCertificate + Ingress) for search-gateway
    "studio-ingress",  # public HTTPS edge (ManagedCertificate + Ingress) for lattice-studio (Studio BFF)
}

# Registry hosts this platform actually publishes to. An image ref pointing anywhere
# else is either third-party (fine) or a mistake (workspace-* pointed at GHCR, which
# CI has never published to — so the pods could only ever ImagePullBackOff).
OUR_REGISTRIES = ("us-central1-docker.pkg.dev/socioprophet-platform/", "registry.socioprophet.ai/")

# Ratchet: pre-existing debt, reported but not failing the build. This exists so the
# gate can be enforced TODAY — blocking every NEW violation — without waiting on debt
# whose fix needs a deliberate, verified rollout rather than a midnight sed.
#
# Keyed by "<service>:<check>", NOT by service. Keying on the service alone would mean
# ratcheting one known problem silently masks every FUTURE, unrelated problem in that
# same service — a hole wearing a gate's clothes.
#
# Entries must carry a reason. The list only ever shrinks: if an entry starts passing,
# the gate FAILS and demands its removal, so it cannot rot into a permanent excuse.
KNOWN_BROKEN = {
    # reasoning-failure-runner:moving-tag is RESOLVED — deploy/values/reasoning-failure-runner.yaml is now pinned
    # to a sha- tag (the Chaos & Resilience Fabric orchestrator, CHAOS_RESILIENCE_FABRIC_V0.md). The ratchet only
    # shrinks: fixed → removed from KNOWN_BROKEN so it can never silently regress to `:latest` again.
    "owl-reasoner:moving-tag": (
        "New service — Dockerfile + images.yml entry added this PR, so it BUILDS. Pin `tag: latest` → the sha- "
        "tag after the first CI build (same chicken-and-egg as grlplus-service/grl-mesh): no sha exists until merge."
    ),
    "entity-resolution:moving-tag": (
        "New service — Dockerfile + images.yml entry added this PR. Pin tag:latest -> sha- after first CI build."
    ),
    "liberty-stack-readout:moving-tag": (
        "New service — liberty-stack-readout vendored into prophet-platform CI this PR. Pin tag:latest -> the "
        "sha- tag after the first build; none exists until merge."
    ),
    "node-commander:moving-tag": (
        "New service — node-commander (node runtime control API) vendored into prophet-platform CI this PR. "
        "Pin tag:latest -> the sha- tag after the first build; none exists until merge."
    ),
    "regis-acr-api:moving-tag": (
        "Build-orphan fixed — regis-acr-api already BUILT in CI but was never in the ApplicationSet; this PR "
        "adds the deploy. Pin tag:latest -> the sha- tag after the next build; none exists for the deploy yet."
    ),
    "memoryd:moving-tag": (
        "New service — memory-mesh's memoryd vendored into prophet-platform CI this PR, so it BUILDS with the "
        "estate WIF. Pin tag:latest -> the sha- tag after the first CI build; no sha exists until merge."
    ),
    "tritfabric-consumption-api:moving-tag": (
        "New service — TritFabric consumption API containerized + wired to prophet-platform CI this PR (it had "
        "app code but no image build). Pin tag:latest -> the sha- tag after the first CI build; none exists yet."
    ),
    "embeddings:moving-tag": (
        "New service — first-party embeddings image (apps/embeddings, FastAPI + nomic-embed-text) added to CI "
        "this PR. Pin tag:latest -> the sha- tag after the first CI build; no sha exists until merge."
    ),
    "algo-engine:moving-tag": (
        "New service — Dockerfile + images.yml entry + values + ApplicationSet added this PR (FastAPI backtests "
        "powering the Algo Trading surface). Pin tag:latest -> the sha- tag after the first CI build; none until merge."
    ),
    "ie-engine:moving-tag": (
        "New service — Dockerfile (spaCy en_core_web_sm baked in) + images.yml + values + ApplicationSet added this "
        "PR (NLP & IE surface, /to-graph writeback into HellGraph). Pin tag:latest -> sha- after the first CI build."
    ),
    # The chart has said "Immutable tag = the commit SHA" since it was written; these
    # 9 predate the check. Pinning them is mechanical BUT NOT SAFE TO BATCH: `latest`
    # + IfNotPresent means nodes may be running an older cached digest than `latest`
    # now resolves to, so pinning ROLLS each service to whatever the newest build is.
    # That is the correct end state and exactly how a latent breakage surfaces — which
    # is why it wants a deliberate pass with per-service verification, not one commit
    # that rolls 9 services at once. Each line here is removed as its service is pinned.
    **{f"{svc}:moving-tag": (
        "Pre-existing `tag: latest`. Pin to the sha- tag the build publishes, then "
        "delete this line. Do it per-service and verify the rollout: pinning changes "
        "which digest actually runs, because the node cache may be older than `latest`."
    ) for svc in [
        "api", "agentic-os-api", "eval-fabric-api",
        "evidence-receipts", "gateway", "osm-map-api",
        "search-orchestrator",
    ]},  # hellgraph-service + evidence-console pinned to immutable sha- tags → removed from the ratchet
}

# Registries that are explicitly not ours. A values file naming one of these is
# declaring "third party, we don't build it" — which is a legitimate answer.
FOREIGN_REGISTRY_RE = re.compile(r"^(docker\.io|ghcr\.io|quay\.io|registry\.k8s\.io|gcr\.io/(?!socioprophet))")



# The chart says it plainly (charts/socioprophet-service/values.yaml):
#     "Immutable tag = the commit SHA the GitOps promotion writes."
# This is that sentence, made executable. Third-party images pin an upstream version
# (v2.164.0) which is immutable by convention — only `latest` is the trap.
MOVING_TAGS = {"latest", "main", "master", "dev", "edge", "stable"}


def check_moving_tag(name: str, image: dict) -> str | None:
    tag = str(image.get("tag") or "").strip()
    if tag.lower() in MOVING_TAGS:
        return (
            f"{name}: image.tag is '{tag}' — a MOVING tag. The chart sets "
            f"imagePullPolicy: IfNotPresent, so once a node caches '{tag}' kubelet "
            f"never pulls a newer one and `rollout restart` re-runs the stale image. "
            f"Pin the immutable sha- tag the build publishes "
            f"(charts/socioprophet-service/values.yaml: 'Immutable tag = the commit SHA')."
        )
    return None


def check_empty_tag(name: str, image: dict) -> str | None:
    """First-party services must PIN a tag; an omitted one is a silent ImagePullBackOff.

    A missing image.tag does not mean `latest` — it falls through to the chart's
    appVersion default (charts/socioprophet-service Chart.yaml, currently 26.11). But
    a first-party build publishes sha-<commit> and latest, never the appVersion, so
    the deploy asks for a tag that was never pushed and the pod ImagePullBackOffs. This
    cost dashboard-bff 108 minutes (#743). The moving-tag check above catches `latest`;
    an empty tag slipped through it because "" is not in MOVING_TAGS.

    Third-party services are exempt: they pin an upstream version (v2.164.0) and are
    handled by the caller's foreign-registry skip before this runs.
    """
    tag = str(image.get("tag") or "").strip()
    if not tag:
        return (
            f"{name}: image.tag is empty/unset — a first-party service must PIN a tag. "
            f"An omitted tag does not mean 'latest'; it inherits the chart's appVersion "
            f"default (26.11), which the build never publishes, so the pod "
            f"ImagePullBackOffs on a tag that does not exist (this is the #743 bug). Set "
            f"the sha- tag the build produces "
            f"(charts/socioprophet-service/values.yaml: 'Immutable tag = the commit SHA')."
        )
    return None


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
                problems.append((f"{name}:wrong-registry",
                    f"{name}: {manifest.relative_to(ROOT)} pulls '{ref}' but CI builds "
                    f"'{repo}' to {OUR_REGISTRIES[0]}… — the pods pull from a registry "
                    f"the image was never published to."
                ))
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
            problems.append((f"{name}:no-values", f"{name}: deployed by an ApplicationSet but deploy/values/{name}.yaml is missing"))
            continue

        data = yaml.safe_load(values_path.read_text(encoding="utf-8")) or {}
        image = data.get("image") or {}
        repository = image.get("repository")
        registry = (image.get("registry") or "").strip()

        if not repository:
            problems.append((f"{name}:no-repository", f"{name}: values has no image.repository"))
            continue

        # A moving tag is wrong for anyone — ours or upstream's.
        moving = check_moving_tag(name, image)
        if moving:
            problems.append((f"{name}:moving-tag", moving))

        if registry and FOREIGN_REGISTRY_RE.match(registry):
            continue  # third-party, we don't build it — legitimately out of scope

        checked += 1
        # First-party only (past the foreign skip): an omitted tag is an ImagePullBackOff.
        empty = check_empty_tag(name, image)
        if empty:
            problems.append((f"{name}:empty-tag", empty))
        if repository not in built:
            problems.append((f"{name}:not-built",
                f"{name}: first-party image '{repository}' has NO entry in images.yml — "
                f"it is deployed but never built, so it can only ImagePullBackOff. "
                f"Add it to the build matrix, pin a foreign image.registry if it is "
                f"third-party, or remove the service from the ApplicationSet."
            ))

    # Split real failures from ratcheted, already-known debt. Keyed by (service, check).
    blocking = [(k, m) for k, m in problems if k not in KNOWN_BROKEN]
    known = [(k, m) for k, m in problems if k in KNOWN_BROKEN]

    print(f"preflight: {len(services)} deployed, {checked} first-party checked against {len(built)} built images")

    if known:
        print("\nKNOWN BROKEN (ratcheted — tracked, not blocking):")
        for k, m in known:
            print(f"  • {m}")
            print(f"      why deferred: {KNOWN_BROKEN[k]}")

    stale = sorted(set(KNOWN_BROKEN) - {k for k, _ in problems})
    if stale:
        print("\nFAIL — these are in KNOWN_BROKEN but now pass. The ratchet only shrinks:", file=sys.stderr)
        for key in stale:
            print(f"  • {key}: now passes — delete it from KNOWN_BROKEN", file=sys.stderr)
        return 1

    if blocking:
        print("\nFAIL — a deployment references something that will never resolve:\n", file=sys.stderr)
        for _, m in blocking:
            print(f"  • {m}", file=sys.stderr)
        return 1

    print("OK: every deployed first-party service is built by CI and pulls from a registry we publish to")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
