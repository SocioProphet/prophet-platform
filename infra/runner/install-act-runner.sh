#!/usr/bin/env bash
# Install a Gitea Actions runner on ANY Linux box.
#
# PHASE 1 target is a GCE VM; PHASE 2 is our own hardware. That migration only
# stays real if this script has nothing Google in it — so it does not:
#   * read the GCP metadata server
#   * use Workload Identity, Secret Manager, or any *.googleapis.com
#   * assume a GCE image, disk layout, or network
# It needs a Linux host with systemd + podman, and outbound HTTPS. Nothing else.
# Phase 2 = run this same script on the anchor box. Not a project — a re-run.
#
# WHY A VM AT ALL: the estate's CI builds images (docker/setup-buildx-action +
# docker/build-push-action), which needs a container runtime with build support.
# The prophet-platform cluster is GKE Autopilot, which REJECTS privileged pods
# outright ("denied by autogke-disallow-privilege" — verified, not assumed), so
# the runner cannot live there. See memory: project_gitea_actions_runner.
#
# WHY NOT GITHUB ACTIONS: that is their software, their policy, their telemetry.
# This is our software on rented metal — a dependency you escape with an scp,
# not a rewrite.
#
# The runner is STATELESS: its only state is the registration token. Destroy the
# box, run this again elsewhere, done.
#
# Usage:
#   GITEA_INSTANCE_URL=https://code.socioprophet.ai \
#   GITEA_RUNNER_TOKEN=<registration token> \
#   [RUNNER_NAME=sovereign-ci-1] \
#   [ACT_RUNNER_IMAGE=registry.socioprophet.ai/gitea/act_runner:<tag>] \
#   sudo -E ./install-act-runner.sh
set -euo pipefail

: "${GITEA_INSTANCE_URL:?set GITEA_INSTANCE_URL (e.g. https://code.socioprophet.ai)}"
: "${GITEA_RUNNER_TOKEN:?set GITEA_RUNNER_TOKEN — mint with: gitea actions generate-runner-token}"
RUNNER_NAME="${RUNNER_NAME:-sovereign-ci-$(hostname -s)}"

# Pull the runner's own image from OUR registry. zot proxies docker.io on demand
# (sync onDemand), so this needs no Docker Hub account and no Docker Hub trust —
# the runner that builds our images is itself served by our registry.
ACT_RUNNER_IMAGE="${ACT_RUNNER_IMAGE:-registry.socioprophet.ai/gitea/act_runner:0.2.11}"

# Labels map a workflow's `runs-on` to how the job executes. `:docker://` runs each
# job in a container (what our workflows expect); podman provides the socket, so no
# privileged DinD daemon is required.
RUNNER_LABELS="${RUNNER_LABELS:-ubuntu-latest:docker://registry.socioprophet.ai/catthehacker/ubuntu:act-22.04,ubuntu-22.04:docker://registry.socioprophet.ai/catthehacker/ubuntu:act-22.04}"

echo "==> installing podman (rootful, for the job socket)"
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq podman uidmap curl ca-certificates
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y -q podman curl ca-certificates
else
  echo "unsupported distro: need apt or dnf" >&2; exit 1
fi

echo "==> enabling the podman socket (the runner talks to this, not to dockerd)"
systemctl enable --now podman.socket
# Our workflows call the docker CLI/API; point DOCKER_HOST at podman's socket.
DOCKER_SOCK=/run/podman/podman.sock

install -d -m 0750 /etc/act_runner /var/lib/act_runner

echo "==> writing runner config"
cat >/etc/act_runner/config.yaml <<YAML
log:
  level: info
runner:
  file: /var/lib/act_runner/.runner
  capacity: 2
  timeout: 3h
  fetch_timeout: 5s
  fetch_interval: 2s
container:
  # podman's socket, not dockerd — Autopilot taught us not to depend on privilege
  docker_host: "unix://${DOCKER_SOCK}"
  privileged: false
  force_pull: false
cache:
  enabled: true
YAML

echo "==> registering with ${GITEA_INSTANCE_URL} as ${RUNNER_NAME}"
podman run --rm \
  -v /etc/act_runner:/etc/act_runner \
  -v /var/lib/act_runner:/var/lib/act_runner \
  -e CONFIG_FILE=/etc/act_runner/config.yaml \
  "${ACT_RUNNER_IMAGE}" \
  act_runner register --no-interactive \
    --instance "${GITEA_INSTANCE_URL}" \
    --token "${GITEA_RUNNER_TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}"

echo "==> installing systemd unit"
cat >/etc/systemd/system/act-runner.service <<UNIT
[Unit]
Description=Gitea Actions runner (sovereign CI)
After=network-online.target podman.socket
Wants=network-online.target

[Service]
Restart=always
RestartSec=5
ExecStart=/usr/bin/podman run --rm --name act-runner \\
  -v /etc/act_runner:/etc/act_runner \\
  -v /var/lib/act_runner:/var/lib/act_runner \\
  -v ${DOCKER_SOCK}:${DOCKER_SOCK} \\
  -e CONFIG_FILE=/etc/act_runner/config.yaml \\
  -e DOCKER_HOST=unix://${DOCKER_SOCK} \\
  ${ACT_RUNNER_IMAGE} act_runner daemon
ExecStop=/usr/bin/podman stop -t 30 act-runner

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now act-runner
sleep 3
systemctl --no-pager --lines=10 status act-runner || true

cat <<EOF

==> done. Verify in Gitea: Site Administration -> Actions -> Runners
    (or per-repo Settings -> Actions -> Runners)

PHASE 2 (off Google): this script is host-agnostic. On the anchor box:
    GITEA_INSTANCE_URL=... GITEA_RUNNER_TOKEN=<new token> sudo -E ./install-act-runner.sh
  then delete the GCE VM. The runner is stateless; nothing to migrate but the token.

COST DISCIPLINE ("we don't leave shit running"): this box only needs to be up when
CI runs. Use a spot/preemptible instance and stop it when idle.
EOF
