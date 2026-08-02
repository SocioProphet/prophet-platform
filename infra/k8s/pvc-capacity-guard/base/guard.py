#!/usr/bin/env python3
"""pvc-capacity-guard — bounded, alerting, automatic growth for estate PVCs.

WHY THIS EXISTS
---------------
On 2026-07-30 `workspace-minio-pvc` reached 100% (20Gi, 184M free). MinIO answered blob
commits with `XMinioStorageFull` (HTTP 507), zot tore down its in-flight `.uploads/`
session, and every image push to registry.socioprophet.ai failed with the very unhelpful
`blob upload unknown to registry`. Four `build (...)` jobs went red on main.

Two independent failures had to line up for that:

  1. Nothing ever expired.   Fixed separately by zot's retention policy (PR #1091).
  2. Nothing warned anyone.  Fixed here.

(2) is the subtle one, and it is NOT "no alert was configured". An alert WAS configured:
kube-prometheus-stack ships `KubePersistentVolumeFillingUp`, and it is loaded and healthy
in the `observability` Prometheus right now. It queries:

    kubelet_volume_stats_available_bytes{job="kubelet", ...}

That Prometheus has **no `kubelet` scrape job at all** — GKE Autopilot's Warden denies
`nodes/proxy` cluster-wide, so kube-prometheus-stack cannot scrape kubelet here. The
metric has zero series, so the rule evaluates an empty set forever and reports
`state=inactive, health=ok, lastError=none` — which is indistinguishable, on every
dashboard, from "the volumes are fine". It was structurally incapable of firing.

So the design constraint is not "add monitoring", it is "add monitoring that is provably
reading real data, on a cluster where the usual source is unavailable".

WHERE THE NUMBERS COME FROM
---------------------------
GKE's *managed* collection does scrape kubelet (monitoringConfig enables the KUBELET and
STORAGE components) and publishes `kubelet_volume_stats_*` into Google Managed Prometheus,
which is queryable over a standard PromQL endpoint. Verified on this cluster: 9 PVC-keyed
series, matching `df` inside the pods.

Deliberately the *same metric names* upstream uses, so if kubelet scraping is ever fixed
in-cluster this can be repointed at the in-cluster Prometheus by changing PROM_BASE alone.

BLIND SPOTS ARE FAILURES, NOT SKIPS
-----------------------------------
A PVC only produces `kubelet_volume_stats_*` while a running pod mounts it. Two estate
PVCs currently produce nothing (`arcticdb-gateway-data` — its pod is in
CreateContainerConfigError; `workspace-mail-backup` — Pending for 12 days). A guard that
silently skips what it cannot see reproduces the exact defect it was built to fix, so an
enrolled PVC with no data is an ALERT, never a skip.

Requires no third-party Python packages: stdlib only.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

GI = 1024 ** 3

# --- endpoints -------------------------------------------------------------------------
PROJECT = os.environ.get("GCP_PROJECT", "socioprophet-platform")
PROM_BASE = os.environ.get(
    "PROM_BASE",
    f"https://monitoring.googleapis.com/v1/projects/{PROJECT}/location/global/prometheus/api/v1",
)
ALERTMANAGER = os.environ.get(
    "ALERTMANAGER_URL",
    "http://kube-prometheus-stack-alertmanager.observability.svc:9093",
)
POLICY_PATH = os.environ.get("POLICY_PATH", "/etc/guard/policy.json")

# Talking to the API server: in-cluster by default, via `kubectl proxy` when testing.
KUBE_PROXY = os.environ.get("KUBE_PROXY")  # e.g. http://127.0.0.1:8001
SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"

DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
# Test seam: force a utilisation reading for one PVC, e.g. "socioprophet/foo=0.93".
# Used to prove the guard fires without waiting for a volume to genuinely fill.
FORCE_UTIL = os.environ.get("FORCE_UTIL", "")

# This guard PATCHES disks off a project-wide datasource, so every query MUST be pinned
# to this cluster. GMP attaches cluster/location to every series; without the matchers a
# second cluster feeding the same project returns kubelet_volume_stats_* that collide on
# the namespace/pvc key, and the guard could resize a volume here off another cluster's
# fill level. Read from env, else the GKE metadata server (same source as gcp_token), so
# it self-scopes in-cluster; unknown scope fails closed in utilisation() rather than
# querying estate-wide.
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "")
CLUSTER_LOCATION = os.environ.get("CLUSTER_LOCATION", "")


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}", flush=True)


# --- auth ------------------------------------------------------------------------------
def gcp_token() -> str:
    """Workload Identity token from the GKE metadata server (or GCP_TOKEN when testing)."""
    tok = os.environ.get("GCP_TOKEN")
    if tok:
        return tok.strip()
    req = urllib.request.Request(
        "http://metadata.google.internal/computeMetadata/v1/"
        "instance/service-accounts/default/token",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["access_token"]


def _metadata_attr(attr: str) -> str:
    """A GKE instance attribute (cluster-name, cluster-location), or "" if the metadata
    server is unreachable (i.e. not on GKE — under test the env vars supply these)."""
    try:
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/attributes/%s" % attr,
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode("utf-8").strip()
    except Exception:  # noqa: BLE001 - absence is expected off-GKE; caller fails closed
        return ""


def cluster_selector() -> str:
    """PromQL label matchers pinning a query to THIS cluster, or "" if it cannot be
    determined. cluster+location uniquely identify a GKE cluster within a project."""
    cluster = CLUSTER_NAME or _metadata_attr("cluster-name")
    if not cluster:
        return ""
    location = CLUSTER_LOCATION or _metadata_attr("cluster-location")
    matchers = ['cluster="%s"' % cluster]
    if location:
        matchers.append('location="%s"' % location)
    return "{%s}" % ", ".join(matchers)


def kube_ctx() -> tuple[str, dict, ssl.SSLContext | None]:
    if KUBE_PROXY:
        return KUBE_PROXY.rstrip("/"), {}, None
    with open(f"{SA_DIR}/token") as fh:
        tok = fh.read().strip()
    ctx = ssl.create_default_context(cafile=f"{SA_DIR}/ca.crt")
    host = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
    port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    return f"https://{host}:{port}", {"Authorization": f"Bearer {tok}"}, ctx


def _http(method: str, url: str, headers: dict, body: bytes | None,
          ctx: ssl.SSLContext | None, timeout: int = 30):
    req = urllib.request.Request(url, method=method, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


# --- signal ----------------------------------------------------------------------------
def promql(query: str) -> list:
    url = f"{PROM_BASE}/query?" + urllib.parse.urlencode({"query": query})
    out = _http("GET", url, {"Authorization": f"Bearer {gcp_token()}"}, None, None)
    if out.get("status") != "success":
        raise RuntimeError(f"PromQL failed: {json.dumps(out)[:300]}")
    return out["data"]["result"]


def utilisation() -> dict[str, float]:
    """{'namespace/pvc': fraction_used}. Empty result is an error, never 'all clear'."""
    sel = cluster_selector()
    if not sel:
        # A mutating guard must never query a project-wide datasource unscoped: another
        # cluster's kubelet_volume_stats_* collide on namespace/pvc and could drive a
        # resize here. Fail closed, same posture as the empty-result guard below.
        raise RuntimeError(
            "cluster scope is unknown — set CLUSTER_NAME/CLUSTER_LOCATION or run on GKE. "
            "Refusing to query kubelet_volume_stats_* estate-wide: GMP is project-wide and "
            "a foreign cluster's series would collide with this cluster's namespace/pvc keys."
        )
    rows = promql(
        f"kubelet_volume_stats_used_bytes{sel} / kubelet_volume_stats_capacity_bytes{sel}"
    )
    if not rows:
        raise RuntimeError(
            "kubelet_volume_stats_* returned ZERO series. Refusing to report 'all clear' "
            "off an empty query — that is precisely how KubePersistentVolumeFillingUp "
            "stayed green while the registry volume hit 100%."
        )
    out = {}
    for r in rows:
        m = r["metric"]
        key = f"{m.get('namespace')}/{m.get('persistentvolumeclaim')}"
        out[key] = float(r["value"][1])
    for override in filter(None, FORCE_UTIL.split(",")):
        k, _, v = override.partition("=")
        out[k.strip()] = float(v)
        log(f"FORCE_UTIL: {k.strip()} treated as {float(v) * 100:.1f}%")
    return out


# --- kubernetes ------------------------------------------------------------------------
def get_pvc(base, hdrs, ctx, ns, name):
    return _http("GET", f"{base}/api/v1/namespaces/{ns}/persistentvolumeclaims/{name}",
                 hdrs, None, ctx)


def grow_pvc(base, hdrs, ctx, ns, name, new_gi: int, annos: dict):
    """Resize AND record bookkeeping in ONE patch.

    This must be a single request. Doing it as two back-to-back patches races the CSI
    external-resizer: it reacts to the size change within milliseconds and patches the
    PVC's status to mark node expansion required, and the second (annotation) patch bumps
    resourceVersion underneath it. Observed exactly that during the fired-proof:

        Warning  VolumeResizeFailed  external-resizer pd.csi.storage.gke.io
          mark PVC ... as node expansion required failed: can't patch status of PVC ...
          Operation cannot be fulfilled ...: the object has been modified; please apply
          your changes to the latest version and try again

    The disk still grew, but the interrupted handshake left the volume needing a pod
    restart to finish the filesystem resize instead of completing online.
    """
    body = json.dumps({
        "metadata": {"annotations": annos},
        "spec": {"resources": {"requests": {"storage": f"{new_gi}Gi"}}},
    }).encode()
    h = dict(hdrs, **{"Content-Type": "application/merge-patch+json"})
    return _http("PATCH", f"{base}/api/v1/namespaces/{ns}/persistentvolumeclaims/{name}",
                 h, body, ctx)


def sc_expandable(base, hdrs, ctx, sc_name: str | None) -> bool:
    """A PVC with no StorageClass is bound to a static PV and can never be expanded."""
    if not sc_name:
        return False
    try:
        sc = _http("GET", f"{base}/apis/storage.k8s.io/v1/storageclasses/{sc_name}",
                   hdrs, None, ctx)
        return bool(sc.get("allowVolumeExpansion"))
    except urllib.error.HTTPError:
        return False


def parse_gi(q: str) -> float:
    units = {"Ki": 1 / (1024 ** 2), "Mi": 1 / 1024, "Gi": 1.0, "Ti": 1024.0,
             "K": 1e3 / GI, "M": 1e6 / GI, "G": 1e9 / GI, "T": 1e12 / GI}
    for suffix, mult in sorted(units.items(), key=lambda kv: -len(kv[0])):
        if q.endswith(suffix):
            return float(q[: -len(suffix)]) * mult
    return float(q) / GI


# --- alerting --------------------------------------------------------------------------
def alert(name: str, severity: str, summary: str, description: str, extra: dict) -> None:
    payload = [{
        "labels": dict({"alertname": name, "severity": severity,
                        "component": "pvc-capacity-guard"}, **extra),
        "annotations": {"summary": summary, "description": description},
        "startsAt": datetime.now(timezone.utc).isoformat(),
    }]
    try:
        _http("POST", f"{ALERTMANAGER}/api/v2/alerts",
              {"Content-Type": "application/json"}, json.dumps(payload).encode(), None, 10)
        log(f"ALERT[{severity}] {name}: {summary}")
    except Exception as exc:  # never let a broken alert path stop remediation
        log(f"ALERT-DELIVERY-FAILED {name}: {exc} :: {summary}")


# --- policy ----------------------------------------------------------------------------
def load_policy() -> dict:
    with open(POLICY_PATH) as fh:
        return json.load(fh)


def main() -> int:
    pol = load_policy()
    d = pol.get("defaults", {})
    thresh = d.get("thresholdPct", 75) / 100.0
    step_pct = d.get("stepPct", 50) / 100.0
    min_step = d.get("minStepGi", 5)
    max_step = d.get("maxStepGi", 50)
    cooldown_s = d.get("cooldownMinutes", 30) * 60
    budget_gi = pol.get("estateMaxTotalGi", 500)

    base, hdrs, ctx = kube_ctx()
    util = utilisation()
    log(f"read {len(util)} PVC utilisation series from GMP")

    # Estate budget is computed over the volumes this guard is allowed to grow.
    #
    # An unreadable enrolled PVC does NOT get silently skipped: that would undercount
    # `provisioned`, and the aggregate brake below (`provisioned - cur + new > budget`)
    # would then pass a grow that actually breaches estateMaxTotalGi — a control reporting
    # headroom it cannot see. So a failed read makes the estate total UNKNOWN, and an
    # unknown budget refuses every grow this cycle (fail closed, same posture as
    # utilisation()'s empty-result guard). Growth resumes once the inventory is readable.
    provisioned = 0.0
    budget_known = True
    budget_blind: list[str] = []
    for ent in pol["pvcs"]:
        try:
            pvc = get_pvc(base, hdrs, ctx, ent["namespace"], ent["name"])
            provisioned += parse_gi(pvc["spec"]["resources"]["requests"]["storage"])
        except Exception as exc:  # noqa: BLE001 - any read failure blinds the total
            budget_known = False
            budget_blind.append(f"{ent['namespace']}/{ent['name']} ({type(exc).__name__})")
    log(f"estate provisioned across guarded PVCs: {provisioned:.0f}Gi / budget {budget_gi}Gi"
        + ("" if budget_known else f" — INCOMPLETE, blind on {len(budget_blind)}"))
    if not budget_known:
        alert("PvcGuardBudgetUnknown", "critical",
              "estate storage budget cannot be computed — refusing all growth this cycle",
              "One or more enrolled PVCs could not be read (" + ", ".join(budget_blind[:5])
              + "), so the estate total is a floor, not the true figure. Growing any volume "
              "now could breach estateMaxTotalGi undetected, so the guard refuses every "
              "expansion until the inventory is readable again. This is the aggregate brake "
              "refusing to act on a number it cannot trust.", {})

    grew = blind = capped = 0

    for ent in pol["pvcs"]:
        ns, name = ent["namespace"], ent["name"]
        key = f"{ns}/{name}"
        max_gi = ent["maxGi"]                       # mandatory: no ceiling, no enrolment
        t = ent.get("thresholdPct", d.get("thresholdPct", 75)) / 100.0

        try:
            pvc = get_pvc(base, hdrs, ctx, ns, name)
        except urllib.error.HTTPError as exc:
            alert("PvcGuardTargetMissing", "warning",
                  f"{key} is enrolled but does not exist",
                  f"HTTP {exc.code} fetching the PVC. Policy and cluster disagree.",
                  {"namespace": ns, "persistentvolumeclaim": name})
            continue

        cur_gi = parse_gi(pvc["spec"]["resources"]["requests"]["storage"])
        annos = (pvc.get("metadata") or {}).get("annotations") or {}

        # -- blind spot: enrolled but no data. Alert; never treat as healthy. ------------
        if key not in util:
            blind += 1
            alert("PvcGuardNoData", "warning",
                  f"{key} is enrolled but reports no utilisation data",
                  "kubelet_volume_stats_* has no series for this PVC — usually its "
                  "consumer pod is not Running (Pending/CreateContainerConfigError), so "
                  "the kubelet publishes nothing. The volume is UNMONITORED: this guard "
                  "cannot grow what it cannot measure.",
                  {"namespace": ns, "persistentvolumeclaim": name})
            continue

        pct = util[key]
        log(f"{key}: {pct * 100:.1f}% of {cur_gi:.0f}Gi (threshold {t * 100:.0f}%, max {max_gi}Gi)")
        if pct < t:
            continue

        # -- non-expandable volumes cannot be helped by this guard ----------------------
        if not sc_expandable(base, hdrs, ctx, pvc["spec"].get("storageClassName")):
            alert("PvcGuardCannotExpand", "critical",
                  f"{key} is {pct * 100:.0f}% full and CANNOT be expanded",
                  "Its StorageClass does not allow volume expansion (or it is bound to a "
                  "static PV with no StorageClass). This needs a manual migration to a "
                  "larger volume — automatic growth is impossible.",
                  {"namespace": ns, "persistentvolumeclaim": name})
            continue

        # -- cooldown: PD resize + filesystem resize is not instantaneous ---------------
        last = annos.get("capacity-guard.socioprophet.ai/last-grown")
        if last:
            try:
                age = time.time() - datetime.fromisoformat(last).timestamp()
                if age < cooldown_s:
                    log(f"  cooldown: grew {age / 60:.0f}m ago (<{cooldown_s / 60:.0f}m), skipping")
                    continue
            except ValueError:
                pass

        # -- already at its ceiling: alert loudly, do NOT grow --------------------------
        if cur_gi >= max_gi:
            capped += 1
            alert("PvcGuardAtMaximum", "critical",
                  f"{key} is {pct * 100:.0f}% full and already at its {max_gi}Gi ceiling",
                  "The capacity guard will NOT grow this volume further. Raise maxGi "
                  "deliberately, or reclaim space (retention/GC). Writes will begin to "
                  "fail when it reaches 100%.",
                  {"namespace": ns, "persistentvolumeclaim": name})
            continue

        # -- bounded step ---------------------------------------------------------------
        step = max(min_step, min(max_step, cur_gi * step_pct))
        new_gi = int(min(cur_gi + step, max_gi))

        # The aggregate brake. An unknown estate total (a PVC read failed above) means we
        # cannot prove this grow stays under budget, so we refuse it — never grow on a
        # number known to be incomplete. PvcGuardBudgetUnknown was already raised once.
        if not budget_known:
            log(f"  budget unknown (incomplete inventory) — refusing to grow {key}")
            continue
        if provisioned - cur_gi + new_gi > budget_gi:
            alert("PvcGuardBudgetExhausted", "critical",
                  f"{key} needs growth but the estate storage budget is exhausted",
                  f"Growing to {new_gi}Gi would put guarded PVCs at "
                  f"{provisioned - cur_gi + new_gi:.0f}Gi against a {budget_gi}Gi budget. "
                  "Refusing. This is the runaway-provisioning brake.",
                  {"namespace": ns, "persistentvolumeclaim": name})
            continue

        if DRY_RUN:
            log(f"  DRY_RUN: would grow {cur_gi:.0f}Gi -> {new_gi}Gi")
            continue

        grow_pvc(base, hdrs, ctx, ns, name, new_gi, {
            "capacity-guard.socioprophet.ai/last-grown":
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "capacity-guard.socioprophet.ai/last-grown-from": f"{cur_gi:.0f}Gi",
        })
        provisioned = provisioned - cur_gi + new_gi
        grew += 1
        # Growth is one-way: a GCE PD can never be shrunk, so every expansion is
        # permanent spend. It gets an alert, not just a log line.
        alert("PvcGuardExpanded", "warning",
              f"{key} grown {cur_gi:.0f}Gi -> {new_gi}Gi ({pct * 100:.0f}% full)",
              f"Automatic expansion by pvc-capacity-guard; ceiling {max_gi}Gi. GCE "
              "persistent disks cannot be shrunk, so this is permanent. Investigate why "
              "the volume is growing — the guard buys time, it does not fix a leak.",
              {"namespace": ns, "persistentvolumeclaim": name})

    log(f"done: grew={grew} at-ceiling={capped} blind={blind} "
        f"checked={len(pol['pvcs'])}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log(f"FATAL: {type(exc).__name__}: {exc}")
        try:
            alert("PvcGuardBroken", "critical", "pvc-capacity-guard run failed",
                  f"{type(exc).__name__}: {exc}. No volume was evaluated this cycle — "
                  "the estate is running without capacity protection.", {})
        except Exception:
            pass
        sys.exit(1)
