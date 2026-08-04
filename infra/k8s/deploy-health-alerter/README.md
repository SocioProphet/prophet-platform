# deploy-health-alerter

The heartbeat for [`tools/deploy_health_alert.py`](../../../tools/deploy_health_alert.py).

The tool reads **live** cluster runtime state and fails on the gaps every *static* deploy gate
misses — a Degraded/Missing ArgoCD app, a stuck or crashlooping pod, a stale/failed job receipt.
That is the class of defect that let `arcticdb-gateway` run broken for ~20h while every static
gate stayed green. But a detection tool nobody schedules is itself the paper control the program
exists to abolish. This CronJob is its heartbeat.

## How it runs
- **CronJob**, every 10 minutes, in the `observability` namespace.
- Bare, digest-pinned `python:3.12-slim` (no kubectl, no pip): the tool is stdlib-only and talks
  to the API server directly over the mounted ServiceAccount token. Script is delivered by a
  name-hashed ConfigMap so a change to the tool shows up as a workload diff in ArgoCD.
- **Read-only RBAC** (`rbac.yaml`): `get`/`list` on pods (all namespaces) and ArgoCD
  applications. No create/patch/delete, no secrets, no GCP identity.

## How findings surface
A non-zero exit (**1** = gaps found, **2** = could-not-observe) fails the Job. Two alerts in
`prometheusrule.yaml`:
- **`DeployHealthGapsDetected`** — the scan is failing: a real, untriaged gap. Read the detail in
  the pod logs (`kubectl -n observability logs job/<latest deploy-health-alerter job>`), then fix
  it or declare a justified `socioprophet.io/deploy-health-hold` on the app.
- **`DeployHealthAlerterNotRunning`** — the CronJob itself stopped completing. Detection is down;
  the alerter has lost its own heartbeat. (The check checks the checker — same discipline as
  `rule-liveness-guard`.)

## How findings become action (the detect→act loop)
The two alerts above were not enough on their own: `DeployHealthGapsDetected` is *binary* —
it fires whenever ANY gap exists — and because the estate always carries some chronic gap it
fires forever and gets ignored. The 2026-08-04 workspace sync-trap proved the cost: three
ArgoCD apps sat OutOfSync for ~40h, flagged every single cycle, into a void.

So findings are also routed to **durable, per-workload GitHub issues**:
- [`tools/deploy_health_to_issues.py`](../../../tools/deploy_health_to_issues.py) reconciles a
  `--json` report into one self-closing issue per `(kind, workload)` gap (label `deploy-health`).
  A chronic gap is one standing issue (not re-fired noise); a NEW gap opens a new issue; a gap
  that CLEARS closes its own issue — the control witnesses its own remediation. A **blind** scan
  (could-not-observe) refuses to reconcile, so nothing is falsely marked resolved.
- [`.github/workflows/deploy-health-detect.yml`](../../../.github/workflows/deploy-health-detect.yml)
  runs the classifier against the live cluster hourly (OIDC/WIF, same as `infra-drift-detect`)
  and drives the reconciler. It routes findings to issues; it does **not** auto-mutate the
  cluster. (Wiring the sociosphere responder to *remediate* — `law_by_kind` — is the next layer.)

## Wiring
- Deployed by [`deploy/argocd/deploy-health-alerter.yaml`](../../../deploy/argocd/deploy-health-alerter.yaml)
  (in the root-recursed `deploy/argocd/` tree; the base stays here).
- `deploy_health_alert.py` in this base is a **mirror** of the canonical `tools/` copy, kept
  byte-identical by `tools/verify_cronjob_script_mirrors.py` (wired into `make validate`).

## Local use
The same tool runs locally against your kube-context (it auto-detects it is *not* in-cluster and
falls back to `kubectl`): `make deploy-health` or `python3 tools/deploy_health_alert.py --self-test`.
