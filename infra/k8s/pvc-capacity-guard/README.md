# pvc-capacity-guard

Bounded, alerting, automatic growth for estate PersistentVolumeClaims.

## Why

On 2026-07-30 `workspace-minio-pvc` hit 100% (20Gi, 184M free). That volume backs both the
workspace object store **and** zot's S3 blob store, so when MinIO started answering blob
commits with `XMinioStorageFull` (HTTP 507), zot tore down its in-flight `.uploads/` session
and every push to `registry.socioprophet.ai` failed with:

```
unknown: blob upload unknown to registry
```

Four `build (...)` jobs went red on `main` — after building successfully. Only the push broke,
so the Dockerfiles looked innocent.

Two independent failures had to line up:

1. **Nothing ever expired.** `storage.gc: true` only reclaims *untagged* blobs, and with no
   retention policy no tag ever became untagged, so GC had nothing to do. Fixed by
   [PR #1091](https://github.com/SocioProphet/prophet-platform/pull/1091) (`storage.retention`
   + `gcInterval: 6h` in `infra/k8s/zot/base/config.json`).
2. **Nothing warned anyone.** Fixed here.

## The part that is not obvious

(2) was *not* "no alert was configured".

kube-prometheus-stack ships `KubePersistentVolumeFillingUp`, and it is loaded and healthy in
the `observability` Prometheus right now — `state=inactive, health=ok, lastError=none`. Its
query is:

```promql
kubelet_volume_stats_available_bytes{job="kubelet", ...} / kubelet_volume_stats_capacity_bytes{job="kubelet", ...} < 0.03
```

That Prometheus has **no `kubelet` scrape job at all**. Its job label values are `apiserver`,
`kube-state-metrics`, `node-exporter`, `otel-collector`, and the stack's own components —
no kubelet. `kubelet_volume_stats_*` resolves to **zero series**, so the rule evaluates an
empty set forever and sits at `inactive` regardless of what the disks are doing. On every
dashboard that is indistinguishable from "the volumes are fine."

The reason is structural: GKE Autopilot's Warden denies `nodes/proxy` cluster-wide —

```
nodes "gk3-..." is forbidden: ... GKE Warden authz [denied by managed-namespaces-limitation]
```

— so kube-prometheus-stack cannot scrape kubelet on this cluster, and neither can any of the
off-the-shelf volume-autoscaler controllers, which all read exactly that metric.

**A capacity guard nobody has watched fire is not a capacity guard.** See "Proving it fires".

## Design

### Why a CronJob and not a controller

Kubernetes has no native PVC autoscaler. The options were:

| Option | Verdict |
|---|---|
| A volume-autoscaler controller (e.g. DevOps-Nirvana/kubernetes-volume-autoscaler) | **Rejected.** Every one of them reads `kubelet_volume_stats_*` from an in-cluster Prometheus. On Autopilot that metric does not exist (above), so the controller would deploy cleanly, report healthy, and never act — reproducing the exact failure mode we are fixing. Making it work would mean first getting kubelet scraping past Warden, which is not in our gift. |
| A CronJob reading usage and patching the PVC | **Chosen.** ~250 lines of stdlib Python, no CRDs, no operator lifecycle, no new failure domain. The reconcile loop for "resize a disk occasionally" does not need to be level-triggered — disks fill over hours, not milliseconds. |

The simplest thing that works, per the brief. A controller would buy continuous reconciliation
we do not need and cost a dependency we cannot satisfy.

### Where the numbers come from

GKE's *managed* collection **does** scrape kubelet (`monitoringConfig` enables the `KUBELET`
and `STORAGE` components) and publishes `kubelet_volume_stats_*` into Google Managed
Prometheus, queryable over a standard PromQL endpoint at
`monitoring.googleapis.com/v1/projects/<p>/location/global/prometheus/api/v1`.

Verified on this cluster: 9 PVC-keyed series whose values match `df` inside the pods.

This is a deliberate GCP dependency and worth naming: the guard reads a Google API. The
counter-argument is that these volumes *are* GCE persistent disks provisioned by
`pd.csi.storage.gke.io` — there is no sovereignty to be had in refusing to read Google's
measurement of Google's disk while running on Google's control plane. The mitigation is that
the guard queries the **same metric names** the upstream rule uses, so if in-cluster kubelet
scraping ever becomes possible, repointing it is a one-line change to `PROM_BASE`.

### Bounds

Growth is one-way — **a GCE persistent disk can never be shrunk** — so every expansion is
permanent spend and the bounds are what keep a runaway push loop from writing a blank cheque.

| Bound | Value | Why |
|---|---|---|
| `thresholdPct` | 75 | PD expansion measured ~25s wall-clock on this cluster (20Gi→100Gi, online, no pod restart). At 75% even the smallest enrolled volume (2Gi) keeps 512Mi of headroom, which outlasts one cycle. 90% would be too late for a burst of image-layer writes. |
| `stepPct` / `minStepGi` / `maxStepGi` | 50% / 5Gi / 50Gi | Geometric so large volumes gain useful headroom; floored so small ones do not creep; **capped so the worst case is 50Gi per cycle = 200Gi/hour**, well inside human reaction time. |
| `maxGi` | per-PVC, **mandatory** | No default and no wildcard. A volume nobody has set a ceiling for is a volume the guard will not grow. At the ceiling it raises `PvcGuardAtMaximum` and stops. |
| `estateMaxTotalGi` | 700 | Aggregate brake. Per-PVC ceilings bound *one* runaway volume; this bounds a *correlated* one. Guarded PVCs total 402Gi today, so this caps worst case at ~1.75x current (~$70/month pd-balanced) — a known number, not an open cheque. |
| `cooldownMinutes` | 30 | Two cycles. A PD resize plus filesystem resize can briefly leave utilisation reading against the old capacity; without this the guard would double-grow on stale data. |
| schedule | `*/15 * * * *` | Paired with the 75% threshold this is the real safety margin: notice and finish expanding before the remaining 25% is consumed. |

### It alerts; it does not silently absorb

Every outcome reaches Alertmanager. Growing a disk is not a success to be swallowed — it is a
symptom.

| Alert | Severity | Meaning |
|---|---|---|
| `PvcGuardExpanded` | warning | A volume was grown. Permanent spend; find out why it is growing. |
| `PvcGuardAtMaximum` | critical | Over threshold and at its ceiling. **The guard has stopped.** Raise `maxGi` deliberately or reclaim space. |
| `PvcGuardCannotExpand` | critical | Over threshold on a volume that can never be expanded (static PV / non-expanding StorageClass). Needs manual migration. |
| `PvcGuardNoData` | warning | Enrolled but reporting nothing — its consumer pod is not Running, so the kubelet publishes no stats. **The volume is unmonitored.** |
| `PvcGuardTargetMissing` | warning | Policy and cluster disagree about a PVC's existence. |
| `PvcGuardBroken` | critical | The run itself failed; no volume was evaluated this cycle. |

`PvcGuardNoData` matters more than it looks. A PVC only produces `kubelet_volume_stats_*`
while a running pod mounts it. Two estate volumes currently produce nothing, so a guard that
*skipped* what it could not see would be silently blind in exactly the way the upstream rule
was. An empty PromQL result is treated as an error, never as "all clear":

```python
if not rows:
    raise RuntimeError("kubelet_volume_stats_* returned ZERO series. Refusing to report
                        'all clear' off an empty query ...")
```

## Proving it fires

A guard nobody has watched fire is the defect class this estate keeps hitting. The loop is
exercised end to end against a real volume — see `docs/` in the PR description for the run
transcript. Reproduce with:

```sh
kubectl proxy --port=8001 &
kubectl -n observability port-forward svc/kube-prometheus-stack-alertmanager 9093:9093 &

# 1Gi probe PVC filled to ~82%, policy maxGi=2
GCP_TOKEN=$(gcloud auth print-access-token) \
KUBE_PROXY=http://127.0.0.1:8001 \
ALERTMANAGER_URL=http://127.0.0.1:9093 \
POLICY_PATH=./probe-policy.json \
python3 infra/k8s/pvc-capacity-guard/base/guard.py
```

`DRY_RUN=1` evaluates and logs without patching. `FORCE_UTIL='ns/pvc=0.93'` overrides one
PVC's reading to exercise a branch without physically filling a disk.

## Prerequisites (not self-contained)

Workload Identity. The `pvc-capacity-guard` KSA in `observability` is annotated for a GCP
service account that needs `roles/monitoring.viewer` to read GMP. **Not created by this
manifest set** — it is a project-level IAM change:

```sh
gcloud iam service-accounts create pvc-capacity-guard --project socioprophet-platform
gcloud projects add-iam-policy-binding socioprophet-platform \
  --member "serviceAccount:pvc-capacity-guard@socioprophet-platform.iam.gserviceaccount.com" \
  --role roles/monitoring.viewer
gcloud iam service-accounts add-iam-policy-binding \
  pvc-capacity-guard@socioprophet-platform.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:socioprophet-platform.svc.id.goog[observability/pvc-capacity-guard]"
```

Until that exists the CronJob will fail at `gcp_token()` and raise `PvcGuardBroken` — loudly,
which is the intended behaviour for an unconfigured guard.

## Volumes this does NOT protect

| PVC | Problem |
|---|---|
| `socioprophet/postgres-data-pvc` | Bound to the static PV `postgres-data-pv` with no StorageClass. **No mechanism can expand it.** The estate's primary database needs a manual migration to dynamic provisioning. Enrolled so it alerts rather than sitting unwatched. |
| `socioprophet/workspace-mail-backup` | Pending for 12 days — its consumer pod never schedules, so it never bound. Also the single highest latent risk in the estate: `mail-backup` writes a **new timestamped full tarball** of the maildir every run and deletes nothing. Fix its retention *before* fixing its scheduling. |
| `socioprophet/arcticdb-gateway-data` | Its pod has been in `CreateContainerConfigError` for ~8h, so no volume stats are published. |

## Related debt this does not fix

The guard buys time. These are the actual leaks:

- **`clickhouse-data`** — the DDL partitions by month across 7 tables but declares **no `TTL`
  clause anywhere**, and nothing drops old partitions.
- **`workspace-mail-pvc`** — Dovecot runs with no quota plugin and no `expire`.
- **`mesh-qdrant`** — the snapshot CronJob writes snapshots onto the same PVC it is snapshotting
  and never calls the delete API. Two bugs currently stop it running; fixing them turns on
  unbounded growth.
- **Alertmanager has no receivers configured**, so today these alerts land in Alertmanager and
  page nobody. Wiring a receiver is the necessary next step for any of this to reach a human.
