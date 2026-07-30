# alert-delivery — the estate's terminal receiver

## What was wrong

Alertmanager had exactly one receiver. It was named `null`.

```yaml
route:
  receiver: "null"
receivers:
  - name: "null"
```

Every alert in this estate — SLO breaches, `KubeJobFailed`, the PVC guard's
data-loss warnings — was routed to a receiver that discards. Nothing reported a
problem, because from inside Alertmanager "delivered to null" and "delivered"
are the same code path. `alertmanager_notifications_total` rose. Dashboards were
green. The whole alerting corpus was decorative.

At the moment this was found, Alertmanager was holding **20 firing alerts** that
no human had ever seen, including four `KubeJobFailed` and a `KubeletDown`.

## What this is

A ~250-line stdlib-Python webhook receiver. Alertmanager POSTs notifications to
it; it turns each alert into an **EvidenceReceipt** (`contracts/EvidenceReceipt.v0.1.json`)
written as one JSON line to stdout.

Deliberately a destination that needs **no credential and no external endpoint**,
so it could be wired tonight without provisioning anything. Human paging is a
separate decision — see *Choosing a human destination* below.

## Where the logs go, and who reads them

| Stream | Lands in | Read by |
|---|---|---|
| Receipts + access + lifecycle (stdout, JSON lines) | `fluentbit-gke` → **Google Cloud Logging** | `gcloud logging read 'resource.labels.container_name="sink"'`; Log Explorer |
| Prometheus counters (`/metrics`) | in-cluster Prometheus via ServiceMonitor | `AlertDeliveryDead`, `AlertSinkDown`, `AlertSinkRejecting` |
| Last 50 deliveries (`/recent`) | process memory, fixed ring | ad-hoc `kubectl exec` during triage |

**Loki is not in that table on purpose.** It is deployed in `observability`, it
is `Running`, it holds a 10Gi PVC — and it has **zero ingested bytes and zero
label values**. Nothing has ever shipped a log line to it. It is another
instance of tonight's defect: a component that runs, reports healthy, and does
nothing. Do not build a logging story on it until something actually writes to
it. Cloud Logging is the estate's only working log sink today.

## Why it cannot silently stop working

A receiver that quietly dies looks exactly like a quiet night. So delivery is
proved continuously rather than assumed:

`kube-prometheus-stack` ships a **`Watchdog`** alert that fires permanently by
design — a dead-man's switch. It is routed here with `repeat_interval: 1h`, so
this process receives a heartbeat every hour, forever.
`alert_sink_notifications_total` must therefore always be rising. If it stops,
**`AlertDeliveryDead`** fires.

That inverts the failure mode: silence is no longer "nothing is wrong", silence
is itself the alarm.

Refusals are equally loud. A malformed payload increments
`alert_sink_errors_total`, emits a receipt with `status: "failed"`, and returns
400 — it is never absorbed. `AlertSinkRejecting` fires on any refusal.

## Bounds

| Bound | Value | Why |
|---|---|---|
| `MAX_BODY_BYTES` | 2 MiB | Caps a single notification. Over-size → 413 + a `denied` receipt. |
| `RECENT_RING` | 50 | Fixed-size ring. The process keeps no unbounded history. |
| `max_alerts` | 0 (never truncate) | Truncating a notification would drop alerts silently — the defect being fixed. |
| Durability | none, by design | Persistence is Cloud Logging's job. This process holds nothing that matters. |

## The two mechanisms, and why both

1. **`deploy/argocd/observability-services.yaml`** sets the Alertmanager
   **default route** to this sink. Estate-wide, all namespaces. Takes effect
   when that Argo app syncs the merged chart values.
2. **`alertmanagerconfig.yaml`** — an `AlertmanagerConfig` CR the operator merges
   in as a sub-route. The operator scopes it to its own namespace
   (`matcherStrategy: OnNamespace`), so it covers `namespace=observability` only.

(2) is a separate resource from the Helm release, so it takes effect without
waiting on a chart sync — and every guard in this wave (`pvc-capacity-guard`,
`rule-liveness-guard`, `alert-delivery`) fires in `observability`. The new
controls therefore have a real receiver from the moment they are applied.

(2) is **not** a substitute for (1): alerts in `socioprophet`, `scm`, `serving`
and cluster-scoped alerts still need the default route.

## Proof it fires

Both directions were observed live, not asserted.

```
$ curl -XPOST localhost:9093/api/v2/alerts -d '[{"labels":{"alertname":"Wave1DeliveryProof",
    "severity":"critical","namespace":"observability"}, ...}]'
POST=200

$ curl localhost:9093/api/v2/alerts | ...
  Wave1DeliveryProof active receivers=[observability/alert-sink/alert-sink]
```

Receipts emitted by the sink, firing then resolved:

```
2026-07-30T05:29:44+00:00  evr-alert-delivered-ee132fdb...  accepted   alert_status=firing
2026-07-30T05:34:44+00:00  evr-alert-delivered-ae71c3a8...  succeeded  alert_status=resolved
```

Counters moved 1 → 2 across the test. Both receipts validate against
`contracts/EvidenceReceipt.v0.1.json` (required fields present, `status` within
the enum, `version` matching the const).

A malformed payload was also exercised: HTTP 400, `alert_sink_errors_total` 0 →
1, and a `status: "failed"` receipt emitted rather than the error being
swallowed.

**The real findings from the `rule-liveness-guard` were then delivered through
this same path** — nine `AlertRuleDead` / `AlertRuleDormant` alerts, receipted
end to end. That run is what caught the inhibition bug described in that
component's README.

## Choosing a human destination — needs a decision

Nothing here pages a person. That is deliberate: every human destination needs a
credential or an external endpoint, which is a provisioning decision, not an
implementation one. The options, with what each costs:

| Destination | Needs | Notes |
|---|---|---|
| **Email via SMTP** | SMTP host + credential | The estate already runs `workspace-mail`/`workspace-smtp` in `socioprophet`. Cheapest path; in-estate, no third party. Recommended first step. |
| **Slack** | Incoming-webhook URL (a secret) | Good ergonomics, external dependency. |
| **PagerDuty / Opsgenie** | Integration key + a paid plan | Only worth it once someone is actually on call. |
| **Google Chat** | Webhook URL | Already inside the Google tenancy. |

Whichever is chosen, the secret must be **minted in CI**, never a personal token,
and referenced from the Alertmanager config by `secretKeyRef`. Until then, the
sink plus Cloud Logging is the record of what fired.

## Runbook

**`AlertDeliveryDead`** — no notification in 3h, so the Watchdog heartbeat has
stopped.

1. `kubectl get pods -n observability -l app=alert-sink` — is it up?
2. `kubectl logs -n observability deploy/alert-sink --tail=50`
3. Check the route did not regress:
   `kubectl get secret -n observability alertmanager-kube-prometheus-stack-alertmanager-generated -o jsonpath='{.data.alertmanager\.yaml\.gz}' | base64 -d | gunzip | grep -A4 '^receivers:'`
   If the only receiver is `"null"`, the Helm values or the AlertmanagerConfig
   have been reverted.
4. `kubectl get alertmanagerconfig -n observability alert-sink`

**Known bound:** if the sink itself is down, the alert saying so cannot be
delivered *to the sink*. It is still visible in Prometheus and Alertmanager, and
`AlertSinkDown` fires there. Closing that loop properly requires an out-of-cluster
receiver — which is the credentialed decision above.
