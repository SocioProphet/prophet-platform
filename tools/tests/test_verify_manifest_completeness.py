"""Teeth for the manifest completeness gate (INV-DEP-11).

INV-DEP-9 resolves analysis-template refs; INV-DEP-10 resolves SA/ConfigMap/PVC refs. This gate
covers the reference classes those two do NOT: Secret refs (must be rendered in-set or allowlisted)
and image digest-pinning (every image must carry a real @sha256 digest). It must PASS the shipped
promote overlays and FAIL a dangling secretRef, a floating-tag image, a placeholder digest, and
malformed YAML (fail-closed). A gate that has only ever passed proves nothing.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_manifest_completeness as chk  # noqa: E402

_GOOD_IMAGE = (
    "us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/search-orchestrator"
    "@sha256:f5b051131d2bc451c4bdd710daaa5261aee45182cc68a840c8ea7539d9d97201"
)

# A Rollout that references a Secret NONE of the rendered docs provide — the class INV-DEP-10 does
# not cover. Image is a real digest so ONLY the secret ref should fail.
ROLLOUT_DANGLING_SECRET = textwrap.dedent(
    f"""
    apiVersion: argoproj.io/v1alpha1
    kind: Rollout
    metadata: {{ name: search-orchestrator, namespace: prophet-platform-prod }}
    spec:
      template:
        spec:
          containers:
            - name: app
              image: {_GOOD_IMAGE}
              envFrom:
                - secretRef: {{ name: search-orchestrator-tls }}
    """
)

# The fixed shape: same Rollout WITH its Secret rendered alongside.
ROLLOUT_SECRET_RENDERED = ROLLOUT_DANGLING_SECRET + textwrap.dedent(
    """
    ---
    apiVersion: v1
    kind: Secret
    metadata: { name: search-orchestrator-tls, namespace: prophet-platform-prod }
    """
)

ROLLOUT_FLOATING_TAG = textwrap.dedent(
    """
    apiVersion: apps/v1
    kind: Deployment
    metadata: { name: search-orchestrator, namespace: prophet-platform-dev }
    spec:
      template:
        spec:
          containers:
            - name: app
              image: us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/search-orchestrator:latest
    """
)

ROLLOUT_PLACEHOLDER_DIGEST = textwrap.dedent(
    """
    apiVersion: apps/v1
    kind: Deployment
    metadata: { name: search-orchestrator, namespace: prophet-platform-dev }
    spec:
      template:
        spec:
          containers:
            - name: app
              image: us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/search-orchestrator@sha256:REPLACE_WITH_FROZEN_DIGEST
    """
)

ROLLOUT_ALLZEROS_DIGEST = textwrap.dedent(
    """
    apiVersion: apps/v1
    kind: Deployment
    metadata: { name: search-orchestrator, namespace: prophet-platform-dev }
    spec:
      template:
        spec:
          containers:
            - name: app
              image: search-orchestrator@sha256:0000000000000000000000000000000000000000000000000000000000000000
    """
)


def test_dangling_secret_ref_fails():
    violations = chk.scan_rendered(ROLLOUT_DANGLING_SECRET, set(), "prod")
    assert any("Secret 'search-orchestrator-tls'" in v and "not found" in v for v in violations), violations


def test_secret_ref_passes_when_rendered():
    assert chk.scan_rendered(ROLLOUT_SECRET_RENDERED, set(), "prod") == []


def test_secret_ref_passes_when_allowlisted():
    assert chk.scan_rendered(ROLLOUT_DANGLING_SECRET, {"search-orchestrator-tls"}, "prod") == []


def test_projected_secret_source_is_checked():
    doc = textwrap.dedent(
        f"""
        apiVersion: apps/v1
        kind: Deployment
        metadata: {{ name: svc, namespace: ns-a }}
        spec:
          template:
            spec:
              containers: [{{ name: app, image: {_GOOD_IMAGE} }}]
              volumes:
                - name: proj
                  projected:
                    sources:
                      - secret: {{ name: missing-secret }}
        """
    )
    violations = chk.scan_rendered(doc, set(), "ns-a")
    assert any("Secret 'missing-secret'" in v for v in violations), violations


def test_image_pull_secret_is_checked():
    doc = textwrap.dedent(
        f"""
        apiVersion: apps/v1
        kind: Deployment
        metadata: {{ name: svc, namespace: ns-a }}
        spec:
          template:
            spec:
              imagePullSecrets:
                - name: gar-pull
              containers: [{{ name: app, image: {_GOOD_IMAGE} }}]
        """
    )
    violations = chk.scan_rendered(doc, set(), "ns-a")
    assert any("Secret 'gar-pull'" in v for v in violations), violations


def test_floating_tag_image_fails():
    violations = chk.scan_rendered(ROLLOUT_FLOATING_TAG, set(), "dev")
    assert any("not digest-pinned" in v for v in violations), violations


def test_placeholder_digest_fails():
    violations = chk.scan_rendered(ROLLOUT_PLACEHOLDER_DIGEST, set(), "dev")
    assert any("PLACEHOLDER digest" in v for v in violations), violations


def test_all_zeros_digest_fails():
    violations = chk.scan_rendered(ROLLOUT_ALLZEROS_DIGEST, set(), "dev")
    assert any("all-zeros" in v for v in violations), violations


def test_real_digest_passes():
    doc = textwrap.dedent(
        f"""
        apiVersion: apps/v1
        kind: Deployment
        metadata: {{ name: svc, namespace: ns-a }}
        spec:
          template:
            spec:
              containers: [{{ name: app, image: {_GOOD_IMAGE} }}]
        """
    )
    assert chk.scan_rendered(doc, set(), "ns-a") == []


def test_init_container_image_is_checked():
    doc = textwrap.dedent(
        f"""
        apiVersion: apps/v1
        kind: Deployment
        metadata: {{ name: svc, namespace: ns-a }}
        spec:
          template:
            spec:
              initContainers:
                - name: migrate
                  image: busybox:1.36
              containers: [{{ name: app, image: {_GOOD_IMAGE} }}]
        """
    )
    violations = chk.scan_rendered(doc, set(), "ns-a")
    assert any("'migrate'" in v and "not digest-pinned" in v for v in violations), violations


def test_no_workload_passes():
    svc_only = "apiVersion: v1\nkind: Service\nmetadata: { name: svc }\n"
    assert chk.scan_rendered(svc_only, set(), "ns-a") == []


def test_malformed_rendered_yaml_fails_closed():
    bad = "kind: Rollout\nspec: template: spec: [ this: not: valid : :\n"
    violations = chk.scan_rendered(bad, set(), "prod")
    assert violations and "not valid YAML" in violations[0]


def test_image_digest_problem_helper():
    assert chk.image_digest_problem(_GOOD_IMAGE) is None
    assert chk.image_digest_problem("repo/app:latest") is not None
    assert chk.image_digest_problem("repo/app@sha256:REPLACE_ME") is not None
    assert chk.image_digest_problem("repo/app@sha256:" + "0" * 64) is not None
    assert chk.image_digest_problem("repo/app@sha256:deadbeef") is not None  # too short
    assert chk.image_digest_problem("repo/app@sha256:" + "z" * 64) is not None  # non-hex


def test_allowlist_loads_from_repo():
    # The shipped allowlist parses and is deny-closed (empty today) — a malformed allowlist would
    # surface an error, never silently allow everything.
    allowed, err = chk.load_external_secret_allowlist(Path(chk.ROOT))
    assert err is None, err
    assert allowed == set()


def test_shipped_promote_overlays_render_complete():
    import shutil

    if shutil.which("kubectl") is None:
        import pytest

        pytest.skip("kubectl not available to render overlays")
    root = Path(chk.ROOT)
    violations = chk.check_overlays(root, chk.DEFAULT_OVERLAYS)
    assert violations == [], f"shipped promote overlays must be reference-complete: {violations}"
