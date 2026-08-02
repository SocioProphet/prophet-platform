"""Teeth for the overlay self-containment gate (INV-DEP-10).

A workload's pod template resolves its serviceAccountName / ConfigMap / PVC by name against its
OWN namespace at pod-create time. This gate must PASS an overlay that renders every object its
workload names, and FAIL one that references a ServiceAccount / ConfigMap / PVC it does not
render — the exact shape that FailedCreate'd on a live prod apply (0 pods). It also proves the
real search-orchestrator promote overlays render self-contained.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_overlay_self_contained as chk  # noqa: E402

# A Rollout naming a non-default SA, a ConfigMap, and a PVC — with NONE of them rendered.
# This is the 2026-08-02 bug shape: "Self-contained" overlay, missing supporting objects.
ROLLOUT_DANGLING = textwrap.dedent(
    """
    apiVersion: argoproj.io/v1alpha1
    kind: Rollout
    metadata: { name: search-orchestrator, namespace: prophet-platform-prod }
    spec:
      template:
        spec:
          serviceAccountName: search-orchestrator
          containers:
            - name: app
              envFrom:
                - configMapRef: { name: search-orchestrator-config }
          volumes:
            - name: data
              persistentVolumeClaim: { claimName: search-orchestrator-data }
    """
)

# The fixed shape: the same Rollout WITH its SA, ConfigMap, and PVC rendered alongside.
ROLLOUT_SELF_CONTAINED = ROLLOUT_DANGLING + textwrap.dedent(
    """
    ---
    apiVersion: v1
    kind: ServiceAccount
    metadata: { name: search-orchestrator, namespace: prophet-platform-prod }
    ---
    apiVersion: v1
    kind: ConfigMap
    metadata: { name: search-orchestrator-config, namespace: prophet-platform-prod }
    ---
    apiVersion: v1
    kind: PersistentVolumeClaim
    metadata: { name: search-orchestrator-data, namespace: prophet-platform-prod }
    """
)


def test_dangling_serviceaccount_fails():
    violations = chk.scan_rendered(ROLLOUT_DANGLING, "prod")
    assert any("serviceAccountName 'search-orchestrator'" in v and "not found" in v for v in violations), violations


def test_dangling_configmap_fails():
    violations = chk.scan_rendered(ROLLOUT_DANGLING, "prod")
    assert any("ConfigMap 'search-orchestrator-config'" in v for v in violations), violations


def test_dangling_pvc_fails():
    violations = chk.scan_rendered(ROLLOUT_DANGLING, "prod")
    assert any("PVC claimName 'search-orchestrator-data'" in v for v in violations), violations


def test_self_contained_passes():
    assert chk.scan_rendered(ROLLOUT_SELF_CONTAINED, "prod") == []


def test_default_serviceaccount_needs_no_render():
    doc = textwrap.dedent(
        """
        apiVersion: apps/v1
        kind: Deployment
        metadata: { name: svc, namespace: ns-a }
        spec:
          template:
            spec:
              serviceAccountName: default
              containers: [{ name: app }]
        """
    )
    assert chk.scan_rendered(doc, "ns-a") == []


def test_configmap_via_projected_volume_is_checked():
    doc = textwrap.dedent(
        """
        apiVersion: apps/v1
        kind: Deployment
        metadata: { name: svc, namespace: ns-a }
        spec:
          template:
            spec:
              containers: [{ name: app }]
              volumes:
                - name: proj
                  projected:
                    sources:
                      - configMap: { name: missing-cm }
        """
    )
    violations = chk.scan_rendered(doc, "ns-a")
    assert any("ConfigMap 'missing-cm'" in v for v in violations), violations


def test_no_workload_passes():
    svc_only = "apiVersion: v1\nkind: Service\nmetadata: { name: svc }\n"
    assert chk.scan_rendered(svc_only, "ns-a") == []


def test_malformed_rendered_yaml_fails_closed():
    bad = "kind: Rollout\nspec: template: spec: [ this: not: valid : :\n"
    violations = chk.scan_rendered(bad, "prod")
    assert violations and "not valid YAML" in violations[0]


def test_shipped_promote_overlays_render_self_contained():
    import shutil

    if shutil.which("kubectl") is None:
        import pytest

        pytest.skip("kubectl not available to render overlays")
    root = Path(chk.ROOT)
    violations = chk.check_overlays(root, chk.DEFAULT_OVERLAYS)
    assert violations == [], f"shipped promote overlays must be self-contained: {violations}"
