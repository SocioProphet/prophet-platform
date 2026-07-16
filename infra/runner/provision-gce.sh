#!/usr/bin/env bash
# PHASE 1 ONLY: put the sovereign CI runner on a GCE VM.
#
# Read this before assuming it contradicts the estate's direction — it is
# deliberate sequencing, decided with Michael 2026-07-15:
#
#   GitHub Actions is THEIR SOFTWARE — their runtime, policy, telemetry, and view
#   of our builds. Escaping it is a rewrite.
#   A GCE VM running OUR act_runner is RENTED METAL. Escaping it is an scp.
#
# So: kill the software lock-in first, the hardware rental second. "We have to use
# Google to kill Google" — but only for one phase, and only because the exit stays
# cheap. That is why install-act-runner.sh has NOTHING Google in it: no metadata
# server, no Workload Identity, no *.googleapis.com. This file is the ONLY
# GCP-shaped thing, and deleting it is the whole of Phase 2.
#
# PHASE 2: run install-act-runner.sh on the anchor box (compute doctrine: small
# federated nodes + own hardware), then `gcloud compute instances delete`. The
# runner is stateless — its only state is a registration token.
#
# WHY NOT ON THE CLUSTER: prophet-platform is GKE Autopilot, which rejects
# privileged pods outright ("denied by autogke-disallow-privilege" — verified).
# The estate's CI builds images, so it needs a real container runtime.
#
# WHY NOT ON THE MAIL VM: never. Mail needs stable IP reputation; CI runs
# semi-untrusted build code. A poisoned build must not be able to touch mail
# deliverability. Different threat models, different boxes.
#
# COST DISCIPLINE: SPOT by default and `--no-restart-on-failure`, because the rule
# is "we tear down all clusters when we are done — we don't leave shit running".
# CI is bursty; stop the box when idle:
#   gcloud compute instances stop  ${VM_NAME} --zone ${ZONE}
#   gcloud compute instances start ${VM_NAME} --zone ${ZONE}
set -euo pipefail

PROJECT="${PROJECT:-socioprophet-platform}"
ZONE="${ZONE:-us-central1-a}"
VM_NAME="${VM_NAME:-sovereign-ci-runner}"
MACHINE="${MACHINE:-e2-standard-2}"   # 2 vCPU / 8GB — buildx needs headroom

: "${GITEA_RUNNER_TOKEN:?mint one first — see README.md in this dir}"
GITEA_INSTANCE_URL="${GITEA_INSTANCE_URL:-https://code.socioprophet.ai}"

echo "==> creating SPOT VM ${VM_NAME} (${MACHINE}) in ${ZONE}"
gcloud compute instances create "${VM_NAME}" \
  --project="${PROJECT}" \
  --zone="${ZONE}" \
  --machine-type="${MACHINE}" \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --no-restart-on-failure \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --boot-disk-type=pd-balanced \
  --scopes=none \
  --no-service-account \
  --labels=purpose=sovereign-ci,phase=1-rented-metal,migrate-to=own-hardware \
  --metadata-from-file=startup-script=<(cat <<EOF
#!/usr/bin/env bash
set -euo pipefail
export GITEA_INSTANCE_URL="${GITEA_INSTANCE_URL}"
export GITEA_RUNNER_TOKEN="${GITEA_RUNNER_TOKEN}"
export RUNNER_NAME="sovereign-ci-gce"
curl -fsSL "${RUNNER_SCRIPT_URL:-https://code.socioprophet.ai/SocioProphet/prophet-platform/raw/branch/main/infra/runner/install-act-runner.sh}" -o /tmp/install-act-runner.sh
bash /tmp/install-act-runner.sh
EOF
)

cat <<EOF

==> created. Note what this VM deliberately does NOT have:
      --no-service-account, --scopes=none  -> it cannot call any Google API.
      It is a dumb Linux box. That is the point: nothing to migrate but the OS.

==> stop it when idle (the rule is: don't leave shit running):
      gcloud compute instances stop ${VM_NAME} --zone ${ZONE} --project ${PROJECT}

==> PHASE 2 (kill this):
      run infra/runner/install-act-runner.sh on the anchor box, then
      gcloud compute instances delete ${VM_NAME} --zone ${ZONE} --project ${PROJECT}
EOF
