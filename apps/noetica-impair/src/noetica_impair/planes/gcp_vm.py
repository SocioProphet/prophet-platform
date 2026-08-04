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
    # Pinned to an immutable sha- tag, NOT :latest. The estate has been bitten by a
    # moving tag under imagePullPolicy: IfNotPresent, where a node keeps serving a
    # cached image and a fix never rolls out. Bump this deliberately.
    image: str = ("us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/"
                  "noetica-impair:sha-f30efd7885622cec0b963c3c184f0ffcedcc595f")
    max_seconds: int = 7200
    service_account: str = "sourceos-ci@socioprophet-platform.iam.gserviceaccount.com"
    scopes: str = "https://www.googleapis.com/auth/cloud-platform"
    preemptible: bool = False
    #: Secret Manager secret holding a HuggingFace read token. The VM's service account
    #: reads it at boot. NOT passed via instance metadata, which is readable by anyone
    #: with instance-get on the project.
    hf_token_secret: str = "hf-token-readonly"
    #: HF repos to stage onto the VM before the container starts. Weights are fetched
    #: HERE, by an explicit and logged step -- the container itself stays
    #: HF_HUB_OFFLINE=1, so the RIG never performs an implicit fetch (invariant 0.6).
    #: Staging on the VM rather than through a laptop avoids an 18GB round trip.
    stage_repos: tuple[str, ...] = ()
    #: Optional per-repo include globs, e.g. one SAE layer out of a 657GB suite.
    stage_includes: tuple[tuple[str, str], ...] = ()
    #: Container command. Defaults to the sweep entrypoint; the discovery pass is a
    #: different module, and hardcoding run_matrix made the GPU plane unable to run the
    #: one pass that gates every SAE preset.
    command: tuple[str, ...] = (
        "python", "-m", "noetica_impair.experiments.run_matrix",
    )
    extra_zones: tuple[str, ...] = field(default_factory=lambda: (
        "us-central1-b", "us-central1-c", "us-east1-c", "us-east4-a", "us-west1-a",
    ))

    def _staging_script(self) -> str:
        """Fetch weights on the VM, before the container starts.

        Three properties this needs and a naive `hf download` would not have:

        * the token comes from Secret Manager via the instance service account, not
          from instance metadata -- metadata is readable by anyone holding
          compute.instances.get on the project;
        * a failed stage ABORTS rather than proceeding, because a run that silently
          finds no weights and falls back would burn the VM's whole budget producing
          nothing, and the fallback would look like a successful empty run;
        * includes are per-repo, because a Gemma Scope SAE repo is ~657GB across every
          layer and width while a run needs exactly one layer's params.npz.
        """
        if not self.stage_repos:
            return ""
        inc = dict(self.stage_includes)
        lines = [
            'mkdir -p /var/impair/weights',
            '# The rig never fetches; the VM stages explicitly and says so in the log.',
            f'HF_TOKEN=$(gcloud secrets versions access latest '
            f'--secret={shlex.quote(self.hf_token_secret)} '
            f'--project={shlex.quote(self.gcp_project)} 2>/dev/null)',
            'if [ -z "${HF_TOKEN:-}" ]; then',
            '  echo "FATAL: could not read the HF token from Secret Manager. The VM '
            'service account needs roles/secretmanager.secretAccessor."; exit 91',
            'fi',
            'export HF_TOKEN',
            # The accelerator image ships python3 but NOT pip, and the first real
            # launch died on `pip: command not found`. Install it if absent, and use
            # `python3 -m pip` rather than a bare `pip` that may not be on PATH.
            'if ! python3 -m pip --version >/dev/null 2>&1; then',
            '  export DEBIAN_FRONTEND=noninteractive',
            '  apt-get update -qq && apt-get install -y -qq python3-pip '
            '|| { echo "FATAL: could not install python3-pip"; exit 92; }',
            'fi',
            'python3 -m pip install --quiet --no-input "huggingface_hub[cli]" '
            '|| python3 -m pip install --quiet --no-input --break-system-packages '
            '"huggingface_hub[cli]" '
            '|| { echo "FATAL: could not install the HF client"; exit 92; }',
            '# hf lands in ~/.local/bin under a user install; make sure it resolves.',
            'export PATH="$PATH:${HOME:-/root}/.local/bin:/usr/local/bin"',
        ]
        for repo in self.stage_repos:
            dest = f"/var/impair/weights/{repo.replace('/', '__')}"
            g = inc.get(repo)
            incl = f" --include {shlex.quote(g)}" if g else ""
            lines += [
                f'echo "staging {repo}{(" (" + g + ")") if g else ""} ..."',
                f'hf download {shlex.quote(repo)}{incl} --local-dir {shlex.quote(dest)} '
                f'--quiet || {{ echo "FATAL: staging {repo} failed"; exit 93; }}',
                f'du -sh {shlex.quote(dest)} || true',
            ]
        lines.append('export IMPAIR_WEIGHTS=/var/impair/weights')
        return "\n".join(lines)

    def startup_script(self, job: RunJob) -> str:
        env = "\n".join(f'export {k}={shlex.quote(v)}' for k, v in sorted(job.to_env().items()))
        staging = self._staging_script()
        cmd = " ".join(shlex.quote(c) for c in self.command)
        log_uri = f"{job.out_uri.rstrip('/')}/{job.name}"
        return f"""#!/usr/bin/env bash
set -uo pipefail

# A metadata startup-script runs with a MINIMAL PATH that does not include /snap/bin.
# On the Ubuntu accelerator image gcloud and gsutil are snaps, so without this every
# `gcloud secrets versions access` returned empty (staging aborted with "could not read
# the HF token") and every cleanup `gsutil cp` silently failed, which is why the first
# runs left no logs in GCS to debug from.
# ${{HOME:-/root}}, not $HOME: a metadata startup-script runs as root with HOME often
# UNSET, and `set -u` turns that into an immediate "unbound variable" abort on line 9.
export PATH="/snap/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${{HOME:-/root}}/.local/bin"
NAME=$(curl -s -H 'Metadata-Flavor: Google' \\
  http://metadata.google.internal/computeMetadata/v1/instance/name)
ZONE=$(curl -s -H 'Metadata-Flavor: Google' \\
  http://metadata.google.internal/computeMetadata/v1/instance/zone | awk -F/ '{{print $NF}}')

# The trap is registered as EARLY as possible, immediately after PATH, and before any
# command that can fail. It used to sit further down: a startup-script abort above it
# (an unbound $HOME under `set -u`) left a GPU instance RUNNING with no work and no
# self-delete, which is the single most expensive failure mode this plane has. A
# self-deleting VM whose self-delete registers late is not self-deleting.
#
# Upload whatever provenance exists, THEN delete. A crashed run must not take its
# receipts down with the box.
cleanup() {{
  gcloud storage cp -r /var/impair/out/* {log_uri}/ 2>/dev/null \\
    || gsutil -m cp -r /var/impair/out/* {log_uri}/ 2>/dev/null || true
  gcloud storage cp /var/log/impair.log {log_uri}/console.log 2>/dev/null \\
    || gsutil cp /var/log/impair.log {log_uri}/console.log 2>/dev/null || true
  gcloud -q compute instances delete "$NAME" --zone "$ZONE" || true
}}
trap cleanup EXIT

exec > >(tee -a /var/log/impair.log) 2>&1
mkdir -p /var/impair/out

# Fail loudly on silent CPU fallback -- a "successful" CPU run of a GPU sweep is the
# expensive kind of wrong.
nvidia-smi || {{ echo "FATAL: no GPU visible"; exit 90; }}

# Docker is assumed by the container step below. The accelerator image may not ship it,
# and discovering that AFTER staging 18.5GB of weights would waste the whole download.
# Check it up front, next to the GPU check, for the same reason.
# Container runtime: docker OR podman, mirroring sourceos-continuum's need_runtime()
# in scripts/dev_up.sh. The estate is podman-first on workstations, and hardcoding
# docker here made this plane the odd one out.
RUNTIME=""
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  RUNTIME=docker
elif command -v podman >/dev/null 2>&1; then
  RUNTIME=podman
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && (apt-get install -y -qq podman || apt-get install -y -qq docker.io) \
    || {{ echo "FATAL: no container runtime and none could be installed"; exit 94; }}
  if command -v podman >/dev/null 2>&1; then RUNTIME=podman; else RUNTIME=docker; systemctl start docker || true; fi
fi
echo "container runtime: $RUNTIME"
$RUNTIME info >/dev/null 2>&1 || {{ echo "FATAL: $RUNTIME present but not usable"; exit 95; }}

# Artifact Registry needs an explicit credential helper. Without it the pull fails with
# exit 125, which reads as a generic runtime error and says nothing about auth -- that
# is exactly what the previous run hit.
ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null || true)
if [ -n "${{ACCESS_TOKEN:-}}" ]; then
  echo "$ACCESS_TOKEN" | $RUNTIME login -u oauth2accesstoken --password-stdin \
    us-central1-docker.pkg.dev >/dev/null 2>&1 \
    || echo "WARNING: registry login failed; the pull may not be authorised"
else
  echo "WARNING: no access token; the registry pull will be anonymous"
fi

{env}
export IMPAIR_OUT=/var/impair/out
export IMPAIR_PLANE=gcp-vm
{staging}

timeout {self.max_seconds} $RUNTIME run --rm --gpus all \\
  -v /var/impair/out:/out \\
  -v /var/impair/weights:/weights:ro \\
  {" ".join(f"-e {k}" for k in sorted(job.to_env()))} \\
  -e IMPAIR_OUT=/out -e IMPAIR_PLANE=gcp-vm -e IMPAIR_WEIGHTS=/weights \\
  {self.image} \\
  {cmd}
echo "container exit=$?"
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
            # GPU instances CANNOT live-migrate: the API rejects the default MIGRATE policy
            # outright ("onHostMaintenance ... must be one of [TERMINATE]"). Every GPU VM
            # must terminate on host maintenance. This plane had never actually created an
            # instance, so the constraint went unnoticed until the first real launch.
            "--maintenance-policy=TERMINATE",
            f"--service-account={self.service_account}",
            f"--scopes={self.scopes}",
            "--metadata-from-file=startup-script=/dev/stdin",
        ]
        if accel:
            # Only n1-* needs this; g2/a2 bundle the GPU and reject the flag.
            # The maintenance policy is set unconditionally ABOVE: it was previously
            # attached to this branch, so a g2 machine -- which bundles its L4 and takes
            # no accelerator flag -- silently kept the default MIGRATE and every create
            # was rejected. The policy is a property of having a GPU at all, not of
            # needing the flag.
            cmd.append(f"--accelerator={accel}")
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
