"""Teeth for the Rollout analysis-ref gate (INV-DEP-9).

A namespaced AnalysisTemplate only resolves for a Rollout in its OWN namespace; a
ClusterAnalysisTemplate resolves everywhere (referenced with clusterScope: true). This gate
must PASS an overlay whose Rollout analysis refs all resolve, and FAIL a dangling ref — a
namespaced template the overlay doesn't render, or a clusterScope ref to an undeclared
ClusterAnalysisTemplate. It also proves the real search-orchestrator promote overlays render
self-contained (against the shipped cluster-scoped slo-gate).
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_rollout_analysis_refs as chk  # noqa: E402

# A blue-green Rollout referencing slo-gate as a CLUSTER-scoped template — the fixed shape.
ROLLOUT_CLUSTER_REF = textwrap.dedent(
    """
    apiVersion: argoproj.io/v1alpha1
    kind: Rollout
    metadata:
      name: search-orchestrator
      namespace: prophet-platform-prod
    spec:
      strategy:
        blueGreen:
          prePromotionAnalysis:
            templates:
              - templateName: slo-gate
                clusterScope: true
            args:
              - { name: service, value: search-orchestrator }
    """
)

# Same Rollout but the ref is NAMESPACED (no clusterScope) and the overlay renders no
# AnalysisTemplate — the exact dangling shape that InvalidSpec'd on a live apply.
ROLLOUT_DANGLING_NS_REF = textwrap.dedent(
    """
    apiVersion: argoproj.io/v1alpha1
    kind: Rollout
    metadata:
      name: search-orchestrator
      namespace: prophet-platform-prod
    spec:
      strategy:
        blueGreen:
          prePromotionAnalysis:
            templates:
              - templateName: slo-gate
    """
)

# A namespaced ref WITH the AnalysisTemplate bundled into the same overlay (Option B shape).
ROLLOUT_NS_REF_WITH_BUNDLED_TEMPLATE = ROLLOUT_DANGLING_NS_REF + textwrap.dedent(
    """
    ---
    apiVersion: argoproj.io/v1alpha1
    kind: AnalysisTemplate
    metadata:
      name: slo-gate
      namespace: prophet-platform-prod
    spec:
      metrics:
        - name: error-ratio
          successCondition: len(result) > 0 && result[0] < 0.05
          failureCondition: len(result) == 0 || result[0] >= 0.05
    """
)


def test_cluster_ref_resolves_when_template_declared():
    # slo-gate declared cluster-wide -> the clusterScope ref resolves from any namespace.
    assert chk.scan_rendered(ROLLOUT_CLUSTER_REF, {"slo-gate"}, "prod") == []


def test_cluster_ref_fails_when_template_not_declared():
    violations = chk.scan_rendered(ROLLOUT_CLUSTER_REF, set(), "prod")
    assert violations, "a clusterScope ref to an undeclared ClusterAnalysisTemplate must fail"
    assert "no ClusterAnalysisTemplate 'slo-gate' is declared" in violations[0]


def test_dangling_namespaced_ref_fails():
    # This is the bug: namespaced ref, overlay renders no AnalysisTemplate. Even with slo-gate
    # declared cluster-wide, a NON-clusterScope ref does not resolve against it.
    violations = chk.scan_rendered(ROLLOUT_DANGLING_NS_REF, {"slo-gate"}, "prod")
    assert violations, "a namespaced ref with no rendered AnalysisTemplate must fail"
    assert "does not render it" in violations[0]
    assert "not found" in violations[0]


def test_namespaced_ref_passes_when_template_bundled():
    # Option B: overlay bundles the namespaced AnalysisTemplate alongside the Rollout.
    assert chk.scan_rendered(ROLLOUT_NS_REF_WITH_BUNDLED_TEMPLATE, set(), "prod") == []


def test_overlay_without_rollout_passes():
    deployment_only = textwrap.dedent(
        """
        apiVersion: apps/v1
        kind: Deployment
        metadata: { name: search-orchestrator, namespace: prophet-platform-canary }
        spec: { replicas: 1 }
        """
    )
    assert chk.scan_rendered(deployment_only, set(), "canary") == []


def test_canary_step_analysis_ref_is_checked():
    canary = textwrap.dedent(
        """
        apiVersion: argoproj.io/v1alpha1
        kind: Rollout
        metadata: { name: svc, namespace: ns-a }
        spec:
          strategy:
            canary:
              steps:
                - setWeight: 20
                - analysis:
                    templates:
                      - templateName: slo-gate
        """
    )
    # namespaced ref, nothing rendered -> fail
    assert chk.scan_rendered(canary, {"slo-gate"}, "canary")


def test_malformed_rendered_yaml_fails_closed():
    bad = "kind: Rollout\nspec: strategy: blueGreen: [ this: is not: valid : :\n"
    violations = chk.scan_rendered(bad, {"slo-gate"}, "prod")
    assert violations, "malformed rendered YAML must not pass silently"
    assert "not valid YAML" in violations[0]


def test_shipped_promote_overlays_render_self_contained():
    # The real overlays, rendered by kubectl kustomize, must pass against the shipped
    # cluster-scoped slo-gate. Skips gracefully if kubectl/kustomize is unavailable.
    root = Path(chk.ROOT)
    declared = chk.discover_cluster_templates(root)
    assert "slo-gate" in declared, "slo-gate must be a declared ClusterAnalysisTemplate"
    import shutil

    if shutil.which("kubectl") is None:
        import pytest

        pytest.skip("kubectl not available to render overlays")
    violations = chk.check_overlays(root, chk.DEFAULT_OVERLAYS)
    assert violations == [], f"shipped promote overlays must be self-contained: {violations}"
