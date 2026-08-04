"""The Kubernetes plane: same Job, local k3s/kind or the cloud twin.

The safety property is the reason this exists in this shape: kubectl's current context
on this estate defaults to the PRODUCTION GKE cluster, so a plane that infers a context
can land a model-degradation run on prod.
"""

from __future__ import annotations

import pytest

from noetica_impair.planes.base import RunJob
from noetica_impair.planes.kube import BACKENDS, KubePlane, UnsafeContextError


def job(**kw):
    kw.setdefault("model_key", "gemma2-9b")
    kw.setdefault("doses", (0.0, 0.6))
    kw.setdefault("seed", 1)
    kw.setdefault("substance", "ALCOHOL")
    return RunJob(**kw)


# ── context safety ───────────────────────────────────────────────────────────

def test_a_context_is_required_and_never_inferred():
    with pytest.raises(UnsafeContextError, match="explicit `context`"):
        KubePlane().plan(job())


def test_the_refusal_explains_the_prod_hazard():
    with pytest.raises(UnsafeContextError) as ei:
        KubePlane().plan(job())
    assert "PRODUCTION" in str(ei.value)


def test_a_prod_looking_context_is_refused_under_the_local_backend():
    p = KubePlane(context="gke_socioprophet-platform_us-central1_prophet-platform",
                  backend="local")
    with pytest.raises(UnsafeContextError):
        p.plan(job())


def test_a_non_local_context_is_refused_when_local_was_claimed():
    with pytest.raises(UnsafeContextError, match="does not look like a"):
        KubePlane(context="some-random-cluster", backend="local").plan(job())


def test_the_kind_context_continuum_creates_is_accepted():
    # scripts/dev_up.sh creates CLUSTER=prophet-paas -> context kind-prophet-paas
    h = KubePlane(context="kind-prophet-paas", backend="local").plan(job())
    assert h.detail["context"] == "kind-prophet-paas"
    assert h.detail["backend"] == "local"


def test_the_twin_is_reachable_by_naming_the_k8s_backend():
    """Production-class targets are allowed, but only when said out loud."""
    h = KubePlane(context="gke_socioprophet-platform_us-central1_twin",
                  backend="k8s").plan(job())
    assert h.submitted is False and h.detail["backend"] == "k8s"


def test_backends_match_the_continuum_capd_vocabulary():
    assert BACKENDS == ("local", "k8s")


# ── the manifest is the SAME either way ──────────────────────────────────────

def test_local_and_twin_produce_the_same_job_shape():
    """Continuum's thesis: the same workload, without seams. Only the context and the
    recorded backend differ."""
    a = KubePlane(context="kind-prophet-paas", backend="local").manifest(job())
    b = KubePlane(context="gke_socioprophet-platform_us-central1_twin",
                  backend="k8s").manifest(job())
    strip = lambda m: {**m, "metadata": {**m["metadata"], "labels": {}}}
    a2, b2 = strip(a), strip(b)
    # containers, command, volumes identical
    ca = a2["spec"]["template"]["spec"]["containers"][0]
    cb = b2["spec"]["template"]["spec"]["containers"][0]
    assert ca["image"] == cb["image"] and ca["command"] == cb["command"]
    assert a2["spec"]["template"]["spec"]["volumes"] == b2["spec"]["template"]["spec"]["volumes"]


def test_a_failed_run_is_a_result_not_a_retry():
    m = KubePlane(context="kind-prophet-paas").manifest(job())
    assert m["spec"]["backoffLimit"] == 0


def test_the_job_cannot_outlive_its_deadline():
    m = KubePlane(context="kind-prophet-paas", max_seconds=1234).manifest(job())
    assert m["spec"]["activeDeadlineSeconds"] == 1234


def test_the_container_runs_unprivileged_with_a_readonly_root():
    c = KubePlane(context="kind-prophet-paas").manifest(job())["spec"]["template"]["spec"]["containers"][0]
    sc = c["securityContext"]
    assert sc["runAsNonRoot"] and sc["readOnlyRootFilesystem"]
    assert sc["allowPrivilegeEscalation"] is False
    assert sc["capabilities"]["drop"] == ["ALL"]


def test_weights_arrive_as_a_readonly_pvc_not_a_runtime_download():
    """Invariant 0.6: the rig never fetches. The image is HF_HUB_OFFLINE=1."""
    m = KubePlane(context="kind-prophet-paas", weights_pvc="gemma-weights").manifest(job())
    c = m["spec"]["template"]["spec"]["containers"][0]
    mount = [v for v in c["volumeMounts"] if v["name"] == "weights"][0]
    assert mount["readOnly"] is True
    vol = [v for v in m["spec"]["template"]["spec"]["volumes"] if v["name"] == "weights"][0]
    assert vol["persistentVolumeClaim"]["readOnly"] is True
    assert {"name": "IMPAIR_WEIGHTS", "value": "/weights"} in c["env"]


def test_no_gpu_request_on_a_local_cluster_by_default():
    """A kind cluster has no GPU; the CPU toy path is what makes local useful."""
    c = KubePlane(context="kind-prophet-paas").manifest(job())["spec"]["template"]["spec"]["containers"][0]
    assert "resources" not in c


def test_gpu_is_requested_when_asked():
    c = KubePlane(context="kind-prophet-paas", gpus=1).manifest(job())["spec"]["template"]["spec"]["containers"][0]
    assert c["resources"]["limits"]["nvidia.com/gpu"] == "1"


def test_the_backend_is_recorded_in_provenance_env():
    c = KubePlane(context="kind-prophet-paas", backend="local").manifest(job())["spec"]["template"]["spec"]["containers"][0]
    assert {"name": "IMPAIR_PLANE", "value": "kube/local"} in c["env"]


def test_the_gke_plane_also_refuses_an_implicit_context():
    """It had no --context at all, so it inherited kubectl's current one — production."""
    import inspect
    from noetica_impair.planes.gke import GKEPlane
    src = inspect.getsource(GKEPlane)
    assert "context" in src
    assert '"--context"' in src, "kubectl must be told which cluster explicitly"


def test_the_capd_declares_the_same_backends_as_the_plane():
    import json, pathlib
    from noetica_impair.planes.kube import BACKENDS
    d = json.loads((pathlib.Path(__file__).parents[1] / "capd/impair-rig.capd.json").read_text())
    assert tuple(d["backends"]) == BACKENDS
    assert "caps.infra.paas.continuum-local@0.1.0" in d["composes_with"]
    # the policy must record the properties the code actually enforces
    for k in ("explicit_target_required", "forbidden_circuit_gated",
              "no_runtime_weight_fetch", "paired_sober_control_required"):
        assert d["policy"][k] is True, f"{k} is enforced in code and must be declared"
