#!/usr/bin/env python3
"""Preflight: every deployed service must reference something that exists.

CI builds images. Nothing checked that the things we DEPLOY line up with the
things we BUILD — so on 2026-07-15 the cluster had ~9 pods crashlooping for two
days behind a 100% green pipeline. Every one of those failures passed CI.

Six checks, all static (no registry credentials, runs anywhere):

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

  5. Every Application carries the FOUNDATION/REFERENCE tier (EdgeX doctrine —
     REQUIRED INTEROPERABILITY FOUNDATION vs REPLACEABLE REFERENCE SERVICES).
     Standalone Applications annotate socioprophet.io/tier directly; ApplicationSets
     stamp it from a per-element `tier:` (fogstack uses `serviceTier:` because its
     matrix already owns `tier` for compliance). Unannotated = FAIL. Nothing
     distinguished contract services from swappable ones, which is how phantom
     mesh services sat in an appset dressed like spine components.

  6. tier=foundation means the image is REBUILDABLE: first-party foundation must be
     built by images.yml, and a ghcr.io/socioprophet reference is never acceptable
     for it — that org is not a registry this platform publishes to anymore, so such
     an image cannot be rebuilt from source here. This is the phantom-deploy class
     caught by the 2026-07-29 audit: agent-registry + model-governance-ledger were
     deployed from ghcr.io/socioprophet/*:latest with no source, no Dockerfile and
     no images.yml entry in this repo — a supply-chain hole shaped like a service.
     Third-party foundation (clickhouse, socbase-auth/rest, minio) stays legal by
     declaring an explicit foreign image.registry pin: that is the deliberate
     "upstream builds this" statement, and checks 3/4 still govern its tags.

  The tier gate proves its own teeth before checking the repo: a hermetic self-test
  rebuilds both failure modes (an unannotated Application; a foundation service
  nothing builds) in a temp fixture on every run and requires them to FAIL. A gate
  that cannot fail is a comment with a green checkmark.

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
    "workspace-mail:wrong-registry": (
        "CAUGHT by the check-6 ghcr.io/socioprophet closure the moment it landed: the mail-backup "
        "CronJob (infra/k8s/workspace-mail/base/backup-cronjob.yaml) pulls "
        "ghcr.io/socioprophet/prophet-platform/workspace-backup:dev — an image never built by "
        "anything, so the DAILY MAIL BACKUP HAS SILENTLY NEVER RUN (ImagePullBackOff since it was "
        "authored). The job is a /bin/sh tar one-liner; the fix is choosing + pinning a real image "
        "(stock busybox via zot, or a first-party backup image in images.yml) and VERIFYING a backup "
        "artifact lands — a deliberate rollout in its own PR, not a drive-by edit inside the tier-"
        "doctrine PR that found it. Ratchet demands removal once fixed."
    ),
    # reasoning-failure-runner:moving-tag is RESOLVED — deploy/values/reasoning-failure-runner.yaml is now pinned
    # to a sha- tag (the Chaos & Resilience Fabric orchestrator, CHAOS_RESILIENCE_FABRIC_V0.md). The ratchet only
    # shrinks: fixed → removed from KNOWN_BROKEN so it can never silently regress to `:latest` again.
    # owl-reasoner:moving-tag is RESOLVED — deploy/values/owl-reasoner.yaml was manually sha-pinned
    # (KKO-TBox build, #974). The ratchet only shrinks: fixed → removed so it can't regress silently.
    # arcticdb-gateway:moving-tag + prophet-materializer-clickhouse:moving-tag are RESOLVED —
    # gitops-promote sha-pinned both values files after their first CI builds (arcticdb-gateway →
    # sha-8fbda01e…, prophet-materializer-clickhouse → sha-4df9dcbd…). The ratchet only shrinks:
    # fixed → removed so neither can silently regress to `:latest` again.
    "market-replay:moving-tag": (
        "New service — Seal-the-Walls W1.2 synthetic MarketDataEvent replay emitter "
        "(apps/market-replay) added to images.yml this PR. Pin tag:latest -> the sha- tag "
        "after the first CI build; no sha exists until merge. Its values set pullPolicy: Always as the "
        "interim guard against the moving-tag+IfNotPresent trap."
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
    # health-twin pinned to a sha- tag by gitops-promote after its first CI build (#932) → removed
    # from the ratchet (it only shrinks).
    # portfolio-agent pinned to a sha- tag by gitops-promote after its first CI build (#925,
    # sha-a6d8311383) → removed from the ratchet (it only shrinks). Same for academy-board:
    # gitops-promote sha-pinned it after #926's first build (sha-f59cf2c9), so its moving-tag
    # entry now passes and is removed.
    # sherlock-engine pinned to a sha- tag by gitops-promote after the 0.0.0.0 bind fix (#887) → removed
    # from the ratchet (it only shrinks). Same for synapse-bridge + holmes: gitops-promote sha-pinned both
    # after their first builds landed (#905/#906), so their moving-tag entries now pass and are removed.
    # algo-engine + ie-engine were pinned to sha- tags by gitops-promote (18f02aad,
    # sha-32f5996a06f6) after their first CI build, so they no longer violate — the
    # ratchet requires removing them here (it only shrinks).
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
    ]},  # hellgraph-service + evidence-console + search-orchestrator (academy sha-pin) → removed from the ratchet
}

# Registries that are explicitly not ours. A values file naming one of these is
# declaring "third party, we don't build it" — which is a legitimate answer.
FOREIGN_REGISTRY_RE = re.compile(r"^(docker\.io|ghcr\.io|quay\.io|registry\.k8s\.io|gcr\.io/(?!socioprophet))")



# The chart says it plainly (charts/socioprophet-service/values.yaml):
#     "Immutable tag = the commit SHA the GitOps promotion writes."
# This is that sentence, made executable. Third-party images pin an upstream version
# (v2.164.0) which is immutable by convention — only `latest` is the trap.
MOVING_TAGS = {"latest", "main", "master", "dev", "edge", "stable"}

# ── Foundation/reference tier doctrine (check 5 + 6) ─────────────────────────
# Annotation stamped on every generated/standalone Application. foundation =
# required interoperability foundation (contract/spine); reference = replaceable
# reference service (swappable implementation). See docstring checks 5-6.
TIER_ANNOTATION = "socioprophet.io/tier"
TIER_VALUES = {"foundation", "reference"}


def _live_lines(text: str) -> str:
    """Drop full-line comments so RETIRED/DEFERRED breadcrumbs never satisfy a gate.

    A commented-out entry is a breadcrumb, not a deployment — the questdb lesson
    ('a comment is a conclusion, not a gate') applied to the parser itself.
    """
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def tier_contract(argocd_dir: Path) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Check 5: every Application under deploy/argocd declares its tier.

    Walks every *.yaml recursively (the root app-of-apps recurses too, so the
    fogstack/ subdirectory is just as deployed as the top level). For standalone
    Applications the socioprophet.io/tier annotation must be literal foundation|
    reference. For ApplicationSets the template must stamp the annotation and
    EVERY list-generator element that names a service must carry tier:/serviceTier:
    with a valid value. Returns (problems, tiers) where tiers maps each element
    name to its declared tier for check 6.
    """
    problems: list[tuple[str, str]] = []
    tiers: dict[str, str] = {}
    for path in sorted(argocd_dir.rglob("*.yaml")):
        rel = path.name
        text = _live_lines(path.read_text(encoding="utf-8"))
        for doc in re.split(r"^---\s*$", text, flags=re.M):
            kind_m = re.search(r"^kind:\s*(ApplicationSet|Application)\s*$", doc, re.M)
            if not kind_m:
                continue
            app_m = re.search(r"^metadata:.*?\bname:\s*([A-Za-z0-9.-]+)", doc, re.S | re.M)
            app = app_m.group(1) if app_m else rel
            if kind_m.group(1) == "Application":
                ann = re.search(rf"{re.escape(TIER_ANNOTATION)}:\s*[\"']?([a-z]+)", doc)
                if not ann or ann.group(1) not in TIER_VALUES:
                    problems.append((f"{app}:untiered-application",
                        f"{rel}: Application '{app}' has no {TIER_ANNOTATION} annotation "
                        f"(foundation|reference). Undeclared tier = nobody can tell a contract "
                        f"service from a swappable one — annotate it (docstring check 5)."
                    ))
                continue
            # ApplicationSet: the template must stamp the annotation on generated apps…
            if not re.search(rf"{re.escape(TIER_ANNOTATION)}:", doc):
                problems.append((f"{app}:untiered-appset-template",
                    f"{rel}: ApplicationSet '{app}' template does not stamp {TIER_ANNOTATION} — "
                    f"generated Applications would carry no tier. Add the annotation to "
                    f"template.metadata.annotations (from the element's tier/serviceTier var)."
                ))
            # …and every service-naming element must declare which tier it is.
            for em in re.finditer(r"^\s*-\s*\{([^}]*)\}", doc, re.M):
                body = em.group(1)
                nm = re.search(r"\bname:\s*([a-z0-9][a-z0-9-]*)", body)
                if not nm:
                    continue  # matrix axis rows (e.g. fogstack's compliance tiers) name no service
                name = nm.group(1)
                tm = re.search(r"\b(?:serviceTier|tier):\s*([a-z]+)", body)
                if not tm or tm.group(1) not in TIER_VALUES:
                    problems.append((f"{name}:no-tier",
                        f"{name}: element in {rel} declares no tier (foundation|reference). "
                        f"Every deployed service states whether it is a contract (foundation) "
                        f"or a swappable implementation (reference) — docstring check 5."
                    ))
                    continue
                tier = tm.group(1)
                if tiers.get(name, tier) != tier:
                    problems.append((f"{name}:tier-conflict",
                        f"{name}: declared '{tiers[name]}' elsewhere but '{tier}' in {rel} — "
                        f"one service, one tier."
                    ))
                tiers[name] = tier
    return problems, tiers


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


def check_kustomize_images(name: str, built: set[str], tier: str | None = None) -> list[str]:
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
            elif ref.startswith("ghcr.io/socioprophet"):
                # Previously a silent fall-through: ours-shaped, never built, never
                # publishable — the exact phantom-deploy shape (docstring check 6).
                check = "foundation-unbuilt" if tier == "foundation" else "wrong-registry"
                problems.append((f"{name}:{check}",
                    f"{name}: {manifest.relative_to(ROOT)} pulls '{ref}' — ghcr.io/socioprophet "
                    f"is not a registry this platform publishes to and '{repo}' has no images.yml "
                    f"build, so the image can never be rebuilt from source here. Vendor the source "
                    f"and add it to the build matrix, or retire the manifest."
                ))
    return problems


def chart_service_problems(
    name: str, values_path: Path, built: set[str], tier: str | None
) -> tuple[list[tuple[str, str]], bool]:
    """All values-file checks for one chart-deployed service.

    Returns (problems, first_party_checked). Factored out of main() so the
    self-test can drive the exact production code path against fixtures.
    """
    problems: list[tuple[str, str]] = []
    if not values_path.exists():
        return [(f"{name}:no-values", f"{name}: deployed by an ApplicationSet but deploy/values/{name}.yaml is missing")], False

    data = yaml.safe_load(values_path.read_text(encoding="utf-8")) or {}
    image = data.get("image") or {}
    repository = image.get("repository")
    registry = (image.get("registry") or "").strip()

    if not repository:
        return [(f"{name}:no-repository", f"{name}: values has no image.repository")], False

    # A moving tag is wrong for anyone — ours or upstream's.
    moving = check_moving_tag(name, image)
    if moving:
        problems.append((f"{name}:moving-tag", moving))

    if registry and FOREIGN_REGISTRY_RE.match(registry):
        # Foreign registry = the deliberate "upstream builds this" declaration —
        # legal even for foundation (clickhouse, socbase-*). One exception:
        # ghcr.io/socioprophet LOOKS foreign to the regex but is this platform's
        # abandoned org — nothing publishes there, so a foundation service pinning
        # it can never be rebuilt. That is the phantom-deploy class (check 6).
        ours_shaped = "socioprophet" in registry or str(repository).startswith("socioprophet/")
        if tier == "foundation" and registry.startswith("ghcr.io") and ours_shaped:
            problems.append((f"{name}:foundation-unbuilt",
                f"{name}: tier=foundation but pulls '{registry}/{repository}' — "
                f"ghcr.io/socioprophet is not published to by this platform, so the image "
                f"cannot be rebuilt from source. Vendor the source + add an images.yml "
                f"entry, or pin a genuine third-party upstream (docstring check 6)."
            ))
        return problems, False

    # First-party (past the foreign skip): an omitted tag is an ImagePullBackOff.
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
        if tier == "foundation":
            problems.append((f"{name}:foundation-unbuilt",
                f"{name}: tier=foundation with NO images.yml build — a REQUIRED "
                f"INTEROPERABILITY FOUNDATION service must be rebuildable from source "
                f"in this repo (docstring check 6: foundation-without-build = FAIL). "
                f"Add '{repository}' to the images.yml matrix or reclassify honestly."
            ))
    return problems, True


def run_self_test() -> None:
    """The gate proves it can FAIL before it certifies anything (docstring tail).

    Rebuilds the two doctrine failure modes in a temp fixture and requires the
    production check functions to reject them. Runs on every invocation — hermetic,
    no repo state touched, so a broken state never needs committing to prove the
    teeth exist.
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="preflight-selftest-") as td:
        root = Path(td)
        argocd = root / "argocd"
        argocd.mkdir()

        # Failure mode A — an Application/element with no tier annotation.
        (argocd / "untiered.yaml").write_text(
            "apiVersion: argoproj.io/v1alpha1\n"
            "kind: ApplicationSet\n"
            "metadata:\n"
            "  name: selftest-untiered\n"
            "spec:\n"
            "  generators:\n"
            "    - list:\n"
            "        elements:\n"
            "          - { name: ghost-svc }\n"
            "  template:\n"
            "    metadata:\n"
            "      name: 'svc-{{.name}}'\n",
            encoding="utf-8",
        )
        problems, _ = tier_contract(argocd)
        keys = {k for k, _ in problems}
        if "ghost-svc:no-tier" not in keys or "selftest-untiered:untiered-appset-template" not in keys:
            print(
                "preflight SELF-TEST FAIL: an unannotated Application no longer fails "
                f"the tier gate (got {sorted(keys) or 'no problems'}) — the gate lost its teeth.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        # Failure mode B — tier=foundation whose image nothing in images.yml builds.
        values = root / "values"
        values.mkdir()
        phantom = values / "phantom-svc.yaml"
        phantom.write_text("image: { repository: phantom-svc, tag: sha-deadbeef }\n", encoding="utf-8")
        fb_problems, _ = chart_service_problems("phantom-svc", phantom, built=set(), tier="foundation")
        fb_keys = {k for k, _ in fb_problems}
        if "phantom-svc:foundation-unbuilt" not in fb_keys:
            print(
                "preflight SELF-TEST FAIL: a foundation-tier service with no images.yml build "
                f"no longer fails (got {sorted(fb_keys) or 'no problems'}) — the gate lost its teeth.",
                file=sys.stderr,
            )
            raise SystemExit(1)

    print("self-test: both doctrine failure modes still FAIL (untiered app; foundation without build) — teeth verified")


def main() -> int:
    run_self_test()

    services = deployed_services()
    built = built_images()
    if not services:
        print("preflight: found no deployed services — check deploy/argocd/", file=sys.stderr)
        return 1

    # Check 5: every Application/element declares foundation|reference.
    problems, tiers = tier_contract(ARGOCD_DIR)
    checked = 0

    for name in sorted(services):
        tier = tiers.get(name)
        if name in NON_CHART_SERVICES:
            problems.extend(check_kustomize_images(name, built, tier))
            continue
        svc_problems, first_party = chart_service_problems(
            name, VALUES_DIR / f"{name}.yaml", built, tier
        )
        problems.extend(svc_problems)
        if first_party:
            checked += 1

    # Split real failures from ratcheted, already-known debt. Keyed by (service, check).
    blocking = [(k, m) for k, m in problems if k not in KNOWN_BROKEN]
    known = [(k, m) for k, m in problems if k in KNOWN_BROKEN]

    n_foundation = sum(1 for t in tiers.values() if t == "foundation")
    n_reference = sum(1 for t in tiers.values() if t == "reference")
    print(
        f"preflight: {len(services)} deployed ({n_foundation} foundation / {n_reference} reference), "
        f"{checked} first-party checked against {len(built)} built images"
    )

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
