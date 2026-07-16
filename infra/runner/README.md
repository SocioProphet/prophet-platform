# Sovereign CI runner

The estate's build/release pipeline is GitHub Actions. **That is the last big piece
of someone else's software in the critical path** — and it is what feeds zot. Until
a Gitea Actions runner exists, the SCM cutover cannot happen: flip the repos first
and the code moves while the pipeline dies.

This directory is that runner.

## The phasing (decided with Michael, 2026-07-15)

Two dependencies get confused as one:

| | What it is | Cost to escape |
|---|---|---|
| **GitHub Actions** | their *software* — runtime, policy, telemetry, their view of our builds | **a rewrite** |
| **A GCE VM running our act_runner** | rented *metal* | **an `scp`** |

So: **kill the software lock-in first, the hardware rental second.** Software
lock-in is the expensive one; hardware is fungible. Phase 1 puts *our* runner on
Google's metal — "we have to use Google to kill Google" — and that is only
acceptable because the exit stays cheap.

**Phase 2 keeps that promise only if we build for it now**, so:

- `install-act-runner.sh` has **nothing Google in it** — no metadata server, no
  Workload Identity, no `*.googleapis.com`. Linux + systemd + podman, that's all.
- `provision-gce.sh` is the **only** GCP-shaped file here. Deleting it *is* Phase 2.
- The VM is created with `--no-service-account --scopes=none` — **it cannot call a
  single Google API.** It is a dumb Linux box on purpose.
- The runner is **stateless**. Its only state is a registration token.

**Phase 2:** run `install-act-runner.sh` on the anchor box (compute doctrine: small
federated nodes + own hardware), then delete the VM. Not a project — a re-run.

## Why not on the cluster

`prophet-platform` is **GKE Autopilot**, which rejects privileged pods outright:

```
denied by autogke-disallow-privilege: container is privileged; not allowed in Autopilot
```

(verified empirically, not assumed). The estate's CI *builds images*
(`docker/setup-buildx-action` + `docker/build-push-action`), so it needs a real
container runtime. Autopilot is excellent for services and wrong for builders —
the same reason **mail** can't live there either (no port 25, no PTR). Expect a
small VM tier alongside the cluster; don't fight Warden.

## Why not on the mail box

**Never.** Mail needs stable IP reputation; CI runs semi-untrusted build code. A
poisoned build must not be able to touch mail deliverability. Different threat
models, different machines.

## Usage

**1. Mint a registration token** (as the `git` user — gitea hard-fails as root
with `mustNotRunAsRoot`):

```sh
POD=$(kubectl -n scm get pods --no-headers | awk '/gitea/{print $1;exit}')
kubectl -n scm exec "$POD" -- su git -c 'gitea actions generate-runner-token'
```

**2. Provision (Phase 1):**

```sh
GITEA_RUNNER_TOKEN=<token> ./provision-gce.sh
```

**3. Or install anywhere (Phase 2 / local / anchor box):**

```sh
GITEA_INSTANCE_URL=https://code.socioprophet.ai \
GITEA_RUNNER_TOKEN=<token> \
sudo -E ./install-act-runner.sh
```

## Cost discipline

The rule is *"we tear down all clusters when we are done — we don't leave shit
running."* CI is bursty. The VM is **SPOT** with `--instance-termination-action=STOP`.
Stop it when idle:

```sh
gcloud compute instances stop  sovereign-ci-runner --zone us-central1-a
gcloud compute instances start sovereign-ci-runner --zone us-central1-a
```

## The loop it closes

The runner pulls **its own image from zot** (`registry.socioprophet.ai/gitea/act_runner`
— zot proxies docker.io on demand, verified HTTP 200) and pushes build results
**back to zot**. Sovereign CI, sovereign image, sovereign registry — with Docker Hub
touched only through our own pull-through cache.
