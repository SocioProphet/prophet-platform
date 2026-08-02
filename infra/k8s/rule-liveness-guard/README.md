# rule-liveness-guard — finds alert rules that cannot fire

## The defect this generalises

`KubePersistentVolumeFillingUp` was loaded in the `observability` Prometheus with
`health=ok`, `lastError=none`, `state=inactive`:

```
group: kubernetes-storage
    KubePersistentVolumeFillingUp | state=inactive | health=ok | lastError=none
```

Its query was
`kubelet_volume_stats_available_bytes{job="kubelet"} / kubelet_volume_stats_capacity_bytes{...} < 0.03`.

That Prometheus has no `kubelet` scrape job — GKE Autopilot's Warden denies
`nodes/proxy` cluster-wide. Both metrics resolve to **zero series**. The rule
evaluated an empty set forever and reported `inactive`, which on every dashboard
is indistinguishable from "the volumes are fine". The disk reached 100%.

That is not one bad rule. **A control that cannot fail is not a control**, and
any rule whose inputs do not exist is in that category. The first scan of this
estate found **28 alerting rules** in that state.

## The signature — and why the obvious test is wrong

"The rule returns nothing" is the wrong test. `up == 0` returns nothing when
everything is up; that is a healthy rule doing its job. The distinguishing
question is whether the rule's **inputs** exist:

```
up == 0                                      ->  `up` has 31 series          -> LIVE
kubelet_volume_stats_available_bytes{job=…}  ->  selector has 0 series       -> DEAD
```

So the guard parses every alerting rule into its **vector selectors** and asks
Prometheus (`/api/v1/series`) whether each matched anything over a lookback
window. A rule whose every selector is empty cannot fire, whatever the cluster
does.

Rules built on `absent()` / `absent_over_time()` are exempt by construction —
reacting to emptiness is their whole purpose.

## Three causes, three verdicts

Collapsing them would produce false positives, so the guard separates them:

| Verdict | Meaning | Severity |
|---|---|---|
| **DEAD-NO-TARGET** | The selector names `job="X"` and `up{job="X"}` has no series. Nothing will ever produce this metric. Structural. | critical |
| **DEAD-LABEL-MISMATCH** | The bare metric *does* exist, but the label matchers exclude every series. Almost always a real bug — a renamed label, or a selector copied from a different topology. | critical |
| **DORMANT** | The metric name has never appeared, but its target is up. Usually a counter created on first occurrence (`*_failures_total`), or a disabled collector. Needs a human decision, not an automatic verdict. | warning |

`HellGraphDown` was caught as **DEAD-LABEL-MISMATCH**: `up{job=~".*hellgraph.*"}`
while `up` had 31 series and none matched.

## Exemptions are declared, justified, and they expire

Some selectors are legitimately absent — Autopilot nodes have no RAID arrays, so
`node_md_disks` will never exist. Those live in `policy.json`. Every entry needs:

- `reason` — why it is absent
- `expires` — a date, after which it **alerts** (`AlertRuleExemptionExpired`)
- `compensating_control` — where the risk still exists, what covers it instead

That last field is the point. `KubePersistentVolumeFillingUp` is exempted, but
only because `pvc-capacity-guard` (PR #1105) reads the same metrics from Google
Managed Prometheus, which *does* scrape kubelet. Two entries deliberately record
that they have **no** compensating control yet and carry short expiries:
`KubePersistentVolumeInodesFillingUp` (inode exhaustion is uncovered) and
`CPUThrottlingHigh` (throttling is unobserved in-cluster).

Expiries are staggered so they do not all come due at once. An allowlist that
never expires just relocates the original problem.

**Not exempted, on purpose:** `HellGraphDown` and `HighErrorRatio`. Both are the
estate's own rules, both are dead, both are fixable rather than acceptable.

## It does not exempt itself

The guard's own alerts (`RuleLivenessGuardNotRunning`, `RuleLivenessGuardFailing`)
are ordinary rules in the same Prometheus and are scanned like everything else.
A scanner that skips itself is how a ratchet ends up counting its own allowlist.

## Failure is loud

Every abnormal outcome raises or alerts; nothing is skipped quietly.

- An expression it cannot parse → `AlertRuleUnscannable`, not a silent skip.
- Prometheus reporting **zero** rules → hard `RuntimeError`. An empty corpus is a
  broken config, never an all-clear.
- A failed `/api/v1/series` lookup → counted as unscannable, not as "live".
- Alertmanager unreachable → `failed` receipt, exit 2.

**Findings do not fail the Job.** The first in-cluster run exited 1 because it
found dead rules, tripped `backoffLimit`, and landed in `BackoffLimitExceeded` —
which would have meant a permanently-red hourly Job for as long as any dead rule
existed, the kind everyone learns to ignore, and would have made
`RuleLivenessGuardFailing` meaningless. Findings travel by **alert**, which is
the channel built for them and which is now actually delivered. A non-zero exit
is reserved for the guard itself being broken.

## Receipts

One `EvidenceReceipt` (`contracts/EvidenceReceipt.v0.1.json`) per scan, as a JSON
line on stdout → `fluentbit-gke` → **Google Cloud Logging**.

```json
{"action":"rule-liveness-scan","status":"partial","service_ref":"infra/k8s/rule-liveness-guard",
 "hash":"96326a03…","hash_algo":"sha256","subject_ref":"prometheus/observability",
 "metrics":{"checked":134,"live":100,"dead":7,"exempted":21,"expired":0,
            "unscannable":0,"absence_based":5,"selectors_tested":197}}
```

`status` is `succeeded` on a clean scan and `partial` when there are findings.
The `hash` covers the canonical finding set, so two scans with identical findings
produce an identical receipt id.

Read them with:

```
gcloud logging read 'resource.labels.container_name="guard"
  AND jsonPayload.action="rule-liveness-scan"' --limit 5
```

## Proof it fires

A probe `PrometheusRule` was applied with three rules: two deliberately dead by
different causes, and one healthy control that returns empty simply because
nothing is down.

**Red:**

```
checked=137 live=101 DEAD=9 exempt=21 expired=0 unscannable=0
  DEAD-NO-TARGET       wave1.probe/ProbeDeadNoTarget       <- no scrape target with job='no-such-exporter'
  DEAD-LABEL-MISMATCH  wave1.probe/ProbeDeadLabelMismatch  <- metric up has 31 series but the label matchers exclude all of them
  DEAD-LABEL-MISMATCH  socioprophet.availability/HellGraphDown
  DORMANT              socioprophet.request-slo/HighErrorRatio
  … 5 more
```

`ProbeLive` was **not** flagged — the control against false positives held.

**Green**, after pointing both probe rules at metrics that exist:

```
checked=137 live=103 DEAD=7 exempt=21 expired=0 unscannable=0
  (no wave1.probe findings)
```

`live` 101 → 103, findings 9 → 7. The probe rule was then deleted.

### The proof caught a bug in this guard

The first non-dry run emitted all nine findings as `AlertRuleDead`, and
Alertmanager **suppressed six of them**:

```
critical  wave1.probe/ProbeDeadNoTarget      state=active     inhibitedBy=0
warning   kube-state-metrics/KubeStateMetr…  state=suppressed inhibitedBy=1
warning   socioprophet.request-slo/HighErr…  state=suppressed inhibitedBy=1
…
```

The stack's default `inhibit_rules` drop `severity=warning` when a
`severity=critical` shares the same `(namespace, alertname)` — and every finding
carries `namespace=observability`. Six real findings were swallowed by a control
that reported success: this guard reproducing, in its own delivery path, exactly
the defect it exists to detect.

Fixed by emitting **distinct alertnames per severity** — `AlertRuleDead`
(critical) and `AlertRuleDormant` (warning) — which cannot inhibit each other.
Re-run confirms all nine `state=active`. Do not merge those names back together.

## Runbook

**`AlertRuleDead` (critical)** — a rule is structurally incapable of firing.
Decide between three actions, in preference order:

1. **Fix the input.** Wrong label, wrong job, a ServiceMonitor that matches
   nothing. This is the usual answer for `DEAD-LABEL-MISMATCH`.
2. **Delete the rule.** If the hazard is not real here, a rule that cannot fire
   is worse than no rule — it reads as coverage.
3. **Declare it** in `policy.json` with a reason, an expiry, and a compensating
   control. Only if the hazard is real but is covered elsewhere.

**`AlertRuleDormant` (warning)** — the target is up but the metric has never
appeared. Confirm whether the metric is created lazily (fine, leave it) or the
collector is disabled (fix or declare it).

**`AlertRuleUnscannable`** — the guard could not parse an expression. That is a
gap in the extractor, not in the rule. File it; do not silence it.
