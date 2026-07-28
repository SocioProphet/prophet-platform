"""GCP VM plane: a self-deleting L4 box, mirroring Noetica's ``gcp-*.sh`` idiom.

This is the cheapest honest path for a sweep and the one the estate already trusts:
``Noetica/agent-machine/scripts/gcp-gpu-eval.sh`` uses ``g2-standard-8`` (1x L4, 24GB),
``gcp-prove-frontier.sh`` pins the accelerator image family, and every one of those
scripts self-deletes with a hard-shutdown guard and streams logs to GCS.

Two properties of that idiom are load-bearing and reproduced here:

* **Self-deletion with a deadline.** A GPU VM left running is the single most
  expensive failure mode in this estate. The startup script deletes the instance in a
  ``trap`` so it dies on success, failure, or crash, and ``MAX_SECONDS`` bounds a hang.
* **Provenance is uploaded before teardown**, so a crashed run still leaves its
  receipts behind rather than taking them down with the box.

``g2-standard-8`` bundles the L4, so it takes no ``--accelerator`` flag -- passing one
is an error. T4/V100 need ``n1-*`` plus an explicit flag. That asymmetry is the thing
people get wrong, so it is encoded rather than commented.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass, field

from .base import ExecutionPlane, PlaneHandle, RunJob

# machine type -> (accelerator flag or None, human label)
ACCELERATORS: dict[str, tuple[str | None, str]] = {
    "g2-standard-8": (None, "L4 24GB (bundled -- no --accelerator flag)"),
    "g2-standard-16": (None, "L4 24GB (bundled)"),
    "n1-standard-8": ("type=nvidia-tesla-t4,count=1", "T4 16GB"),
    "a2-ultragpu-1g": (None, "A100 80GB (bundled)"),
}

IMAGE_FAMILY = "ubuntu-accelerator-2204-amd64-with-nvidia-580"
IMAGE_PROJECT = "ubuntu-os-accelerator-images"


@dataclass
class GCPVMPlane(ExecutionPlane):
    name: str = "gcp-vm"
    gcp_project: str = "socioprophet-platform"
    zone: str = "us-central1-a"
    machine_type: str = "g2-standard-8"
    boot_disk_gb: int = 200
    image: str = "us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/noetica-impair:latest"
    max_seconds: int = 7200
    service_account: str = "sourceos-ci@socioprophet-platform.iam.gserviceaccount.com"
    scopes: str = "https://www.googleapis.com/auth/cloud-platform"
    preemptible: bool = False
    extra_zones: tuple[str, ...] = field(default_factory=lambda: (
        "us-central1-b", "us-central1-c", "us-east1-c", "us-east4-a", "us-west1-a",
    ))

    def startup_script(self, job: RunJob) -> str:
        env = "\n".join(f'export {k}={shlex.quote(v)}' for k, v in sorted(job.to_env().items()))
        log_uri = f"{job.out_uri.rstrip('/')}/{job.name}"
        return f"""#!/usr/bin/env bash
set -uo pipefail
NAME=$(curl -s -H 'Metadata-Flavor: Google' \\
  http://metadata.google.internal/computeMetadata/v1/instance/name)
ZONE=$(curl -s -H 'Metadata-Flavor: Google' \\
  http://metadata.google.internal/computeMetadata/v1/instance/zone | awk -F/ '{{print $NF}}')

# Upload whatever provenance exists, THEN delete. A crashed run must not take its
# receipts down with the box.
cleanup() {{
  gsutil -m cp -r /var/impair/out/* {log_uri}/ 2>/dev/null || true
  gsutil cp /var/log/impair.log {log_uri}/console.log 2>/dev/null || true
  gcloud -q compute instances delete "$NAME" --zone "$ZONE" || true
}}
trap cleanup EXIT

exec > >(tee -a /var/log/impair.log) 2>&1
mkdir -p /var/impair/out

# Fail loudly on silent CPU fallback -- a "successful" CPU run of a GPU sweep is the
# expensive kind of wrong.
nvidia-smi || {{ echo "FATAL: no GPU visible"; exit 90; }}

{env}
export IMPAIR_OUT=/var/impair/out
export IMPAIR_PLANE=gcp-vm

timeout {self.max_seconds} docker run --rm --gpus all \\
  -v /var/impair/out:/out \\
  {" ".join(f"-e {k}" for k in sorted(job.to_env()))} \\
  -e IMPAIR_OUT=/out -e IMPAIR_PLANE=gcp-vm \\
  {self.image} \\
  python -m noetica_impair.experiments.run_matrix
echo "run_matrix exit=$?"
"""

    def create_command(self, job: RunJob) -> list[str]:
        if self.machine_type not in ACCELERATORS:
            raise ValueError(
                f"unknown machine type {self.machine_type!r}; known: {sorted(ACCELERATORS)}"
            )
        accel, _label = ACCELERATORS[self.machine_type]
        cmd = [
            "gcloud", "compute", "instances", "create", job.name,
            f"--project={self.gcp_project}",
            f"--zone={self.zone}",
            f"--machine-type={self.machine_type}",
            f"--image-family={IMAGE_FAMILY}",
            f"--image-project={IMAGE_PROJECT}",
            f"--boot-disk-size={self.boot_disk_gb}GB",
            "--boot-disk-type=pd-balanced",
            f"--service-account={self.service_account}",
            f"--scopes={self.scopes}",
            "--metadata-from-file=startup-script=/dev/stdin",
        ]
        if accel:
            # Only n1-* needs this; g2/a2 bundle the GPU and reject the flag.
            cmd.append(f"--accelerator={accel}")
            cmd.append("--maintenance-policy=TERMINATE")
        if self.preemptible:
            cmd.append("--preemptible")
        return cmd

    def plan(self, job: RunJob) -> PlaneHandle:
        cmd = self.create_command(job)
        script = self.startup_script(job)
        artifact = (
            "# startup-script\n" + script + "\n\n# create\n"
            + " \\\n  ".join(shlex.quote(c) for c in cmd)
        )
        return PlaneHandle(
            plane=self.name, job_name=job.name, submitted=False, artifact=artifact,
            out_uri=f"{job.out_uri.rstrip('/')}/{job.name}",
            detail={
                "machine_type": self.machine_type,
                "accelerator": ACCELERATORS[self.machine_type][1],
                "zone": self.zone,
                "self_deleting": True,
                "max_seconds": self.max_seconds,
                "fallback_zones": list(self.extra_zones),
            },
        )

    def submit(self, job: RunJob) -> PlaneHandle:
        h = self.plan(job)
        if shutil.which("gcloud") is None:
            raise RuntimeError("gcloud not found; use plan() and run the command yourself")
        proc = subprocess.run(
            self.create_command(job), input=self.startup_script(job),
            text=True, capture_output=True, check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"instance create failed (try a fallback zone {self.extra_zones}): "
                f"{proc.stderr.strip()}"
            )
        h.submitted = True
        h.detail["gcloud"] = proc.stdout.strip()
        return h
