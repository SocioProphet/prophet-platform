"""Kubernetes plane: the same Job, local k3s/kind or the cloud twin.

This is the continuum thesis applied to the rig. ``sourceos-continuum`` owns "onboard →
develop → cloud-native test → rollout ... the same workload, without seams, from n=1
local up to a composable cluster". A run that only exists as a bespoke cloud VM script
is exactly the seam that repo exists to remove -- and debugging it cost five VM boots,
each one a several-minute round trip for a failure a local cluster would have shown in
seconds.

So there is one manifest and one code path. The only thing that changes between a
laptop and the twin is the kube CONTEXT.

``backends`` mirrors ``capd/compute-plane.mesh.capd.json``: ``local`` (kind/k3s on
podman) and ``k8s`` (the cloud twin). Same Job either way.

── The safety property that made this worth building ────────────────────────

**A context is REQUIRED and never inferred.** kubectl's current context on this estate
defaults to the PRODUCTION GKE cluster. A plane that shells out to a bare
``kubectl apply`` inherits that, so a rig whose whole purpose is to degrade a model --
ablating refusal circuits among other things -- would land on prod because someone
forgot to switch context. ``GKEPlane`` has this bug today; it never passes ``--context``
at all.

Refusing to guess is the entire point. There is no default, no "current context"
fallback, and a context whose name is not recognisably local or twin is rejected rather
than assumed benign.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from .base import ExecutionPlane, PlaneHandle, RunJob

#: Mirrors capd/compute-plane.mesh.capd.json's backend vocabulary.
BACKENDS = ("local", "k8s")

#: Contexts we will knowingly submit to. A kind cluster created by continuum's
#: scripts/dev_up.sh is named `kind-prophet-paas`; k3s contexts are conventionally
#: `k3s-*` or `default` on the node itself.
LOCAL_CONTEXT_HINTS = ("kind-", "k3s", "rancher-desktop", "docker-desktop", "minikube")

#: Names that indicate a production cluster. Submitting a degradation experiment here
#: is never what anyone meant.
PROD_CONTEXT_HINTS = ("prophet-platform", "gke_", "prod", "production")


class UnsafeContextError(RuntimeError):
    pass


@dataclass
class KubePlane(ExecutionPlane):
    """Run the rig as a Job on an EXPLICITLY named cluster."""

    name: str = "kube"
    #: No default. Naming the cluster is the operator's decision, not a guess.
    context: str | None = None
    backend: str = "local"
    namespace: str = "noetica-impair"
    image: str = ("us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/"
                  "noetica-impair:sha-f30efd7885622cec0b963c3c184f0ffcedcc595f")
    #: Only meaningful on a GPU-bearing cluster; a local kind cluster has none, and the
    #: rig's CPU toy path is what makes local useful for plumbing.
    gpus: int = 0
    accelerator: str | None = None
    weights_pvc: str | None = None
    max_seconds: int = 5400
    command: tuple[str, ...] = (
        "python", "-m", "noetica_impair.experiments.run_matrix",
    )
    extra_env: dict[str, str] = field(default_factory=dict)

    # ── context safety ───────────────────────────────────────────────────────

    def _require_context(self) -> str:
        if not self.context:
            raise UnsafeContextError(
                "KubePlane requires an explicit `context`. It is deliberately not "
                "inferred: kubectl's current context on this estate is the PRODUCTION "
                "GKE cluster, and a run that degrades a model must never land there by "
                "default. Pass the kind/k3s context for local, or the twin's context."
            )
        low = self.context.lower()
        if any(h in low for h in PROD_CONTEXT_HINTS) and self.backend != "k8s":
            raise UnsafeContextError(
                f"context {self.context!r} looks like production but backend is "
                f"{self.backend!r}. If you genuinely mean a production-class cluster, "
                "set backend='k8s' explicitly so the choice is recorded."
            )
        if self.backend == "local" and not any(h in low for h in LOCAL_CONTEXT_HINTS):
            raise UnsafeContextError(
                f"backend='local' but context {self.context!r} does not look like a "
                f"local cluster (expected one of {LOCAL_CONTEXT_HINTS}). Refusing to "
                "guess -- rename the context or set the backend you actually mean."
            )
        return self.context

    # ── manifest ─────────────────────────────────────────────────────────────

    def manifest(self, job: RunJob) -> dict[str, Any]:
        env = [{"name": k, "value": v} for k, v in sorted(job.to_env().items())]
        env += [{"name": k, "value": v} for k, v in sorted(self.extra_env.items())]
        env.append({"name": "IMPAIR_PLANE", "value": f"kube/{self.backend}"})

        container: dict[str, Any] = {
            "name": "impair",
            "image": self.image,
            "command": list(self.command),
            "env": env,
            # The platform runs containers as uid 10001 with a read-only root fs; the
            # image already expects emptyDirs at /cache and /tmp.
            "securityContext": {
                "runAsUser": 10001,
                "runAsNonRoot": True,
                "allowPrivilegeEscalation": False,
                "readOnlyRootFilesystem": True,
                "capabilities": {"drop": ["ALL"]},
            },
            "volumeMounts": [
                {"name": "cache", "mountPath": "/cache"},
                {"name": "tmp", "mountPath": "/tmp"},
                {"name": "out", "mountPath": "/out"},
            ],
        }
        volumes: list[dict[str, Any]] = [
            {"name": "cache", "emptyDir": {}},
            {"name": "tmp", "emptyDir": {}},
            {"name": "out", "emptyDir": {}},
        ]

        if self.gpus:
            container["resources"] = {"limits": {"nvidia.com/gpu": str(self.gpus)}}
        if self.weights_pvc:
            # Weights arrive as a PVC rather than a runtime download: the image is
            # HF_HUB_OFFLINE=1 and invariant 0.6 says the rig never fetches.
            container["volumeMounts"].append(
                {"name": "weights", "mountPath": "/weights", "readOnly": True})
            volumes.append({"name": "weights",
                            "persistentVolumeClaim": {"claimName": self.weights_pvc,
                                                      "readOnly": True}})
            container["env"].append({"name": "IMPAIR_WEIGHTS", "value": "/weights"})

        spec: dict[str, Any] = {
            "restartPolicy": "Never",
            "containers": [container],
            "volumes": volumes,
        }
        if self.accelerator:
            spec["nodeSelector"] = {"cloud.google.com/gke-accelerator": self.accelerator}
            spec["tolerations"] = [{"key": "nvidia.com/gpu", "operator": "Exists",
                                    "effect": "NoSchedule"}]

        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job.name,
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/name": "noetica-impair",
                    "noetica.ai/backend": self.backend,
                },
            },
            "spec": {
                "backoffLimit": 0,          # a failed run is a result, not a retry
                "activeDeadlineSeconds": self.max_seconds,
                "ttlSecondsAfterFinished": 3600,
                "template": {"metadata": {"labels": {
                    "app.kubernetes.io/name": "noetica-impair"}}, "spec": spec},
            },
        }

    # ── lifecycle ────────────────────────────────────────────────────────────

    def plan(self, job: RunJob) -> PlaneHandle:
        ctx = self._require_context()
        return PlaneHandle(
            plane=self.name, job_name=job.name, submitted=False,
            detail={
                "context": ctx, "backend": self.backend, "namespace": self.namespace,
                "gpus": self.gpus, "weights_pvc": self.weights_pvc,
                "manifest": self.manifest(job),
            },
        )

    def submit(self, job: RunJob) -> PlaneHandle:
        h = self.plan(job)
        if shutil.which("kubectl") is None:
            raise RuntimeError("kubectl not found; use plan() and apply the manifest yourself")
        proc = subprocess.run(
            ["kubectl", "--context", h.detail["context"], "apply", "-f", "-"],
            input=json.dumps(h.detail["manifest"]), text=True,
            capture_output=True, check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"kubectl apply failed: {proc.stderr.strip()}")
        h.submitted = True
        h.detail["kubectl"] = proc.stdout.strip()
        return h
