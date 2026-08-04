# resource-contract-producer

The heartbeat for [`tools/emit_resource_contracts.py`](../../../tools/emit_resource_contracts.py) —
the **evidence half** of the resource-sufficiency loop.

The tool reads live cluster state (declared limits, observed peak usage from metrics-server,
OOMKill counts) and emits schema-valid `ResourceContract`s + `SufficiencyVerdict`s. Run by hand it
*proves* the loop; on a schedule it *is* the loop. A tool nobody schedules leaves every verdict
stale — the silent-staleness this program refuses.

## How it runs
- **CronJob**, every 30 minutes, in `observability`; scans the `socioprophet` workloads.
- Bare, digest-pinned `python:3.12-slim`: stdlib-only, reads the Kubernetes + `metrics.k8s.io`
  APIs directly over the mounted ServiceAccount token (no kubectl). Script via a name-hashed
  ConfigMap.
- **Read-only RBAC**: `get`/`list` on pods, `apps/deployments`, and `metrics.k8s.io/pods`. No
  mutate, no secrets, no GCP identity.
- **Alert**: `ResourceContractProducerNotRunning` fires if the CronJob stops completing — the
  loop's evidence would otherwise go stale unnoticed.

## Publishing (best-effort)
Each contract is wrapped as a `resource_contract` `EventEnvelope` and POSTed to the devsecops mesh
(`--publish-url`). **Emission always completes; a publish failure is logged, not fatal.**

> ⚠️ **Consumer-side gap (tracked, not owned here):** the devsecops mesh is Kafka-configured
> (`kafka.eventbus.svc`), but no `eventbus`/Kafka broker is currently deployed, so nothing yet
> *consumes* the published contracts. The producer's half is complete and correct; standing up the
> mesh broker (or enabling the in-process HTTP ingest on a deployed gdi) is the completing step.
> See the SOTA backlog.

## Wiring
- Deployed by [`deploy/argocd/resource-contract-producer.yaml`](../../../deploy/argocd/resource-contract-producer.yaml).
- The script here is a **mirror** of the `tools/` canonical, kept byte-identical by
  `tools/verify_cronjob_script_mirrors.py` (`make validate`).

## Local use
`python3 tools/emit_resource_contracts.py --namespace socioprophet` (auto-detects it is not
in-cluster and uses `kubectl get --raw`).
