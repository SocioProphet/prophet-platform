"""GKE plane: run a sweep as a Kubernetes batch Job with a GPU.

Grounded in what prophet-platform actually has, not what would be convenient:

* The primary GKE cluster is **Autopilot** (``infra/tofu/environments/gcp-gke``) with
  NO explicit GPU node pool -- Autopilot auto-provisions on an ``nvidia.com/gpu``
  request, so the request itself is the provisioning trigger. The nodeSelector below
  picks the accelerator type; the toleration matches the standard GPU taint used by
  ``deploy/training/gpu-train-job.yaml``.
* ``charts/socioprophet-service`` renders Deployments ONLY -- there is no Job template
  and no ApplicationSet for batch work. So this plane emits a manifest for
  ``kubectl apply``, matching how every existing GPU workload here is run. Registering
  it in ArgoCD would mean adding a Kustomize path under ``infra/k8s/`` plus an
  ApplicationSet element, which is the house convention for non-Deployment workloads.
* The container image is built by ``.github/workflows/images.yml``, where the image
  name MUST equal the ``apps/<dir>`` name because ``gitops-promote`` keys off that.

One real constraint worth flagging: the service chart defaults to
``readOnlyRootFilesystem: true``, and a transformers run needs a writable HF cache.
This manifest mounts an explicit ``emptyDir`` at ``HF_HOME`` rather than relaxing the
security context.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

import yaml

from .base import ExecutionPlane, PlaneHandle, RunJob

DEFAULT_IMAGE = "us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/noetica-impair"


@dataclass
class GKEPlane(ExecutionPlane):
    name: str = "gke"
    namespace: str = "training"
    image: str = DEFAULT_IMAGE
    image_tag: str = "latest"
    accelerator: str = "nvidia-l4"
    gpus: int = 1
    cpu: str = "6"
    memory: str = "32Gi"
    ttl_seconds: int = 3600
    service_account: str = ""

    def manifest(self, job: RunJob) -> dict:
        env = [{"name": k, "value": v} for k, v in sorted(job.to_env().items())]
        env.append({"name": "HF_HOME", "value": "/cache/hf"})
        # Weights are pulled from GCS by the entrypoint; never fetched from the hub.
        env.append({"name": "HF_HUB_OFFLINE", "value": "1"})
        env.append({"name": "TRANSFORMERS_OFFLINE", "value": "1"})

        spec = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job.name,
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/name": "noetica-impair",
                    "app.kubernetes.io/part-of": "socioprophet",
                    "impair/model": job.model_key,
                    "impair/substance": (job.substance or job.topical_stimulus or "sober").lower(),
                },
            },
            "spec": {
                "backoffLimit": 1,
                "ttlSecondsAfterFinished": self.ttl_seconds,
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        # Autopilot auto-provisions a GPU node from this pair.
                        "nodeSelector": {"cloud.google.com/gke-accelerator": self.accelerator},
                        "tolerations": [{
                            "key": "nvidia.com/gpu", "operator": "Exists", "effect": "NoSchedule",
                        }],
                        "containers": [{
                            "name": "impair",
                            "image": f"{self.image}:{self.image_tag}",
                            "command": ["python", "-m", "noetica_impair.experiments.run_matrix"],
                            "env": env,
                            "resources": {
                                "limits": {
                                    "nvidia.com/gpu": str(self.gpus),
                                    "cpu": self.cpu,
                                    "memory": self.memory,
                                },
                            },
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "runAsNonRoot": True,
                                "runAsUser": 10001,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            # HF cache + scratch, because the platform's baseline is a
                            # read-only root filesystem.
                            "volumeMounts": [
                                {"name": "cache", "mountPath": "/cache"},
                                {"name": "tmp", "mountPath": "/tmp"},
                            ],
                        }],
                        "volumes": [
                            {"name": "cache", "emptyDir": {"sizeLimit": "64Gi"}},
                            {"name": "tmp", "emptyDir": {"sizeLimit": "8Gi"}},
                        ],
                    }
                },
            },
        }
        if self.service_account:
            spec["spec"]["template"]["spec"]["serviceAccountName"] = self.service_account
        return spec

    def plan(self, job: RunJob) -> PlaneHandle:
        return PlaneHandle(
            plane=self.name, job_name=job.name, submitted=False,
            artifact=yaml.safe_dump(self.manifest(job), sort_keys=False),
            out_uri=job.out_uri,
            detail={"namespace": self.namespace, "accelerator": self.accelerator},
        )

    def submit(self, job: RunJob) -> PlaneHandle:
        h = self.plan(job)
        if shutil.which("kubectl") is None:
            raise RuntimeError("kubectl not found; use plan() and apply the manifest yourself")
        proc = subprocess.run(
            ["kubectl", "apply", "-f", "-"], input=h.artifact,
            text=True, capture_output=True, check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"kubectl apply failed: {proc.stderr.strip()}")
        h.submitted = True
        h.detail["kubectl"] = proc.stdout.strip()
        return h
