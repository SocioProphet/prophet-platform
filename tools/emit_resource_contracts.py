#!/usr/bin/env python3
"""Emit REAL ResourceContracts + SufficiencyVerdicts from the live cluster — the producer
half of the producer -> consumer -> learning loop for sourceos-spec's Measurement +
ResourceContract.

Until now the loop was DECLARED (schemas merged, devsecops maps them, sociosphere recognises
the verdict) but not FLOWING: nothing emitted a real ResourceContract. This does. For every
workload it reads the declared limit, MEASURES the observed peak from metrics-server, reads
whether enforcement actually fired, and emits:

  * a ResourceContract  (sourceos-spec/schemas/ResourceContract.json shape)
  * a SufficiencyVerdict (the algebra in global-devsecops-intelligence/mappings/
    resource-contract-measurement-telemetry-v1.yaml — PROVED / VIOLATION / INCONCLUSIVE)

ready for the ops.evidence.artifacts.v1 / ops.learning.feedback.v1 topics.

Honesty is the whole point, so the tool refuses to overclaim:

  * observedPeak is `source: measured` (instrument: metrics-server) taken as the MAX over N
    samples in a stated window. A single sample would under-represent the true peak; N samples
    with `sampling.observed=N` is honest about the window it actually saw.
  * MEMORY has a real enforcement signal: the limit is enforced by OOMKill (terminate), and the
    OOMKilled count is readable from pod lastState. So memory verdicts are real.
  * CPU is enforced by throttling, but the throttle counter (cgroup cpu.stat nr_throttled) is
    not exposed through the k8s API — so fired_count is UNKNOWN. Rather than fake PROVED, a CPU
    contract whose peak is under limit is INCONCLUSIVE, and the Measurement records that the
    throttle signal was not collected. (Wire Prometheus/cAdvisor cpu.stat to make CPU real.)
  * a workload with NO limit cannot carry a ResourceContract at all — it is UNBOUNDED, a
    resource control that does not exist. That is emitted as an explicit governance gap, not
    silently skipped: the never-declared control is as much a finding as the never-fired one.

Verdict algebra (identical to the devsecops mapping, reimplemented so the producer and the
consumer independently agree):
  not gate-eligible                                   -> INCONCLUSIVE
  enforcing mode AND fired_count > 0                  -> PROVED
  enforcing mode AND peak > limit AND fired_count==0  -> VIOLATION
  otherwise                                           -> INCONCLUSIVE

Usage:  python3 tools/emit_resource_contracts.py [--namespace socioprophet] [--samples 3]
        [--interval 8] [--out /tmp/resource-contracts]
Read-only against the cluster. Exit 0 always (it reports; it is a producer, not a gate) unless
kubectl/metrics are unreachable, which is INCONCLUSIVE for everything and exits 2.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _kubectl(args: list[str]) -> str:
    return subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=60).stdout


# ── data access: in-cluster REST (CronJob, no kubectl) or local kubectl ───────
# As a scheduled in-cluster CronJob there is no kubectl binary, so the producer reads the API
# server directly over the mounted ServiceAccount token via stdlib urllib — the same pattern as
# infra/k8s/pvc-capacity-guard/base/guard.py. Everything (deployments, pods, pod metrics) is
# pulled through the API, so local and in-cluster share one JSON parse path.
_SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"


def in_cluster() -> bool:
    return bool(os.environ.get("KUBERNETES_SERVICE_HOST")) and os.path.isfile(f"{_SA_DIR}/token")


def _api_get(path: str) -> dict | None:
    try:
        with open(f"{_SA_DIR}/token", encoding="utf-8") as fh:
            token = fh.read().strip()
        ctx = ssl.create_default_context(cafile=f"{_SA_DIR}/ca.crt")
        host = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
        port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
        req = urllib.request.Request(f"https://{host}:{port}{path}",
                                     headers={"Authorization": f"Bearer {token}",
                                              "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            return json.load(r)
    except (OSError, urllib.error.URLError, ValueError) as e:
        sys.stderr.write(f"[producer] in-cluster GET {path} failed: {e}\n")
        return None


def _get_raw(path: str) -> dict | None:
    """GET a Kubernetes API path as JSON — in-cluster REST, else `kubectl get --raw`."""
    if in_cluster():
        return _api_get(path)
    try:
        r = subprocess.run(["kubectl", "get", "--raw", path], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def envelope(contract: dict) -> dict:
    """Wrap a ResourceContract as an EventEnvelope the devsecops consumer ingests.

    type=resource_contract is the key the resource-contract-measurement-telemetry mapping
    consumes to derive TelemetrySignal/EvidenceArtifact/SufficiencyVerdict onto the ops.* topics.
    """
    now = datetime.now(timezone.utc)
    return {
        "timestamp": int(now.timestamp() * 1000),                       # ms, for bus ordering
        "utc_timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        "type": "resource_contract",
        "data": contract,
        "data_name": contract.get("contractId", "resource_contract"),
    }


def publish(url: str, contracts: list[dict]) -> tuple[int, int]:
    """Best-effort POST each contract as an EventEnvelope. Returns (ok, failed).

    Publishing is best-effort by design: EMISSION (the evidence) is the producer's primary job
    and always completes; if the mesh endpoint is unreachable or has ingest off, the contracts
    are still in the logs and --out. A publish failure never fails the run.
    """
    ok = failed = 0
    for c in contracts:
        body = json.dumps(envelope(c)).encode()
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                ok += 1 if 200 <= r.status < 300 else 0
                failed += 0 if 200 <= r.status < 300 else 1
        except (urllib.error.URLError, OSError) as e:
            failed += 1
            if failed <= 2:
                sys.stderr.write(f"[producer] publish to {url} failed: {e}\n")
    return ok, failed


def _cpu_to_millicores(v: str) -> float | None:
    if not v:
        return None
    v = v.strip()
    try:
        if v.endswith("m"):
            return float(v[:-1])
        if v.endswith("n"):          # nanocores (metrics-server sometimes)
            return float(v[:-1]) / 1e6
        if v.endswith("u"):          # microcores
            return float(v[:-1]) / 1e3
        return float(v) * 1000.0     # whole cores
    except ValueError:
        return None


_MEM_UNITS = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
              "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}


def _mem_to_bytes(v: str) -> float | None:
    if not v:
        return None
    v = v.strip()
    for u, mult in _MEM_UNITS.items():
        if v.endswith(u):
            try:
                return float(v[: -len(u)]) * mult
            except ValueError:
                return None
    try:
        return float(v)
    except ValueError:
        return None


def expected_verdict(*, peak, limit, fired_count, gate_eligible, enforcement) -> str:
    """The SufficiencyVerdict algebra — identical to the devsecops mapping's validator."""
    if not gate_eligible:
        return "INCONCLUSIVE"
    if enforcement != "observe" and fired_count and fired_count > 0:
        return "PROVED"
    if enforcement != "observe" and peak is not None and limit is not None \
            and peak > limit and (fired_count == 0):
        return "VIOLATION"
    return "INCONCLUSIVE"


def sample_peaks(ns: str, samples: int, interval: float) -> tuple[dict, int]:
    """MAX cpu(millicores)/mem(bytes) per pod over `samples` reads. Returns (peaks, taken).

    Sourced from the metrics.k8s.io API (the same data `kubectl top` prints), summed across a
    pod's containers, so the code path is identical locally and in-cluster. metrics-server
    reports cpu in nanocores and memory in Ki — both handled by the converters.
    """
    peaks: dict[str, dict[str, float]] = {}
    taken = 0
    for i in range(samples):
        data = _get_raw(f"/apis/metrics.k8s.io/v1beta1/namespaces/{ns}/pods")
        items = (data or {}).get("items") or []
        if items:
            taken += 1
            for pm in items:
                pod = pm.get("metadata", {}).get("name", "")
                cpu_tot, mem_tot = 0.0, 0.0
                for c in pm.get("containers", []):
                    usage = c.get("usage", {}) or {}
                    cpu, mem = _cpu_to_millicores(usage.get("cpu", "")), _mem_to_bytes(usage.get("memory", ""))
                    if cpu is not None:
                        cpu_tot += cpu
                    if mem is not None:
                        mem_tot += mem
                d = peaks.setdefault(pod, {"cpu": 0.0, "mem": 0.0})
                d["cpu"] = max(d["cpu"], cpu_tot)
                d["mem"] = max(d["mem"], mem_tot)
        if i < samples - 1:
            time.sleep(interval)
    return peaks, taken


def cpu_throttle_by_pod(prometheus_url: str, ns: str, window_s: float) -> dict[str, float] | None:
    """Throttled CFS periods per pod over the window, from Prometheus (cAdvisor). None on failure.

    This is the missing CPU enforcement signal: `container_cpu_cfs_throttled_periods_total` is the
    number of scheduler periods in which the container was throttled because it hit its CPU limit.
    The k8s API does not expose it, which is why CPU verdicts are INCONCLUSIVE without this — the
    limit's teeth are simply unobserved. `increase(...[window])` > 0 means throttling FIRED.
    None (query failed) is distinct from {} (queried, nothing throttled): the caller keeps CPU
    INCONCLUSIVE on None, but can reach PROVED/VIOLATION on a real {} / positive result.
    """
    win = max(int(window_s), 60)
    q = (f'sum by (pod) (increase(container_cpu_cfs_throttled_periods_total'
         f'{{namespace="{ns}"}}[{win}s]))')
    url = prometheus_url.rstrip("/") + "/api/v1/query?query=" + urllib.parse.quote(q)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}),
                                    timeout=15) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, ValueError) as e:
        sys.stderr.write(f"[producer] prometheus throttle query failed: {e}\n")
        return None
    if data.get("status") != "success":
        return None
    out: dict[str, float] = {}
    for res in data.get("data", {}).get("result", []):
        pod = (res.get("metric") or {}).get("pod", "")
        try:
            val = float((res.get("value") or [None, "0"])[1])
        except (TypeError, ValueError):
            continue
        # Prometheus returns NaN/Inf for absent or divide-by-zero series; int(NaN) would later
        # raise and crash EMISSION, which must never happen for a best-effort signal. Drop them.
        if not math.isfinite(val):
            continue
        out[pod] = val
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", default="socioprophet")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--interval", type=float, default=8.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--publish-url", default="",
                    help="POST each contract as a resource_contract EventEnvelope to a mesh "
                         "ingest URL (best-effort; emission always completes regardless)")
    ap.add_argument("--prometheus-url", default="",
                    help="Prometheus base URL to read the CPU throttle signal "
                         "(container_cpu_cfs_throttled_periods_total). Without it, CPU stays "
                         "INCONCLUSIVE — the throttle counter is not on the k8s API.")
    args = ap.parse_args()
    ns = args.namespace

    deploys_doc = _get_raw(f"/apis/apps/v1/namespaces/{ns}/deployments")
    if not deploys_doc or not (deploys_doc.get("items")):
        print("cluster API unreachable or no deployments — everything INCONCLUSIVE", file=sys.stderr)
        return 2
    deploys = deploys_doc["items"]

    window_s = args.interval * max(args.samples - 1, 0)
    peaks, taken = sample_peaks(ns, args.samples, args.interval)
    metrics_ok = taken > 0

    # OOMKilled count per workload (memory enforcement FIRED), from pod lastState.
    pods = (_get_raw(f"/api/v1/namespaces/{ns}/pods") or {"items": []}).get("items", [])
    oom: dict[str, int] = {}
    pod_peak: dict[str, dict] = peaks
    def owner(podname: str) -> str:
        # strip the two trailing ReplicaSet/pod hash segments: <deploy>-<rs>-<pod>
        return "-".join(podname.split("-")[:-2]) if podname.count("-") >= 2 else podname
    for p in pods:
        nm = p["metadata"]["name"]
        for cs in p.get("status", {}).get("containerStatuses", []):
            if cs.get("lastState", {}).get("terminated", {}).get("reason") == "OOMKilled":
                oom[owner(nm)] = oom.get(owner(nm), 0) + 1

    # CPU throttle count per workload (CPU enforcement FIRED), from Prometheus if wired.
    # throttle is None when unavailable (CPU stays INCONCLUSIVE) vs a dict when queried.
    throttle_by_pod = cpu_throttle_by_pod(args.prometheus_url, ns, window_s) if args.prometheus_url else None
    wl_throttle: dict[str, float] | None = None
    if throttle_by_pod is not None:
        wl_throttle = {}
        for pod, cnt in throttle_by_pod.items():
            wl_throttle[owner(pod)] = wl_throttle.get(owner(pod), 0.0) + cnt

    # aggregate pod peaks -> workload peaks
    wl_peak: dict[str, dict] = {}
    for pod, d in pod_peak.items():
        w = owner(pod)
        agg = wl_peak.setdefault(w, {"cpu": 0.0, "mem": 0.0})
        agg["cpu"] = max(agg["cpu"], d["cpu"])
        agg["mem"] = max(agg["mem"], d["mem"])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contracts, verdicts, unbounded = [], [], []
    tally = {"PROVED": 0, "VIOLATION": 0, "INCONCLUSIVE": 0}

    for w in deploys:
        name = w["metadata"]["name"]
        c = w["spec"]["template"]["spec"]["containers"][0]
        lim = c.get("resources", {}).get("limits", {}) or {}
        peak = wl_peak.get(name, {"cpu": 0.0, "mem": 0.0})

        specs = []
        if lim.get("memory"):
            specs.append(("memory", "bytes", _mem_to_bytes(lim["memory"]), peak["mem"],
                          "terminate", oom.get(name, 0)))          # OOMKill = real fired signal
        if lim.get("cpu"):
            # throttle FIRED signal from Prometheus if wired; None keeps CPU INCONCLUSIVE (the
            # counter is not on the k8s API). A workload with a CPU limit but no throttle series
            # yet has fired 0 (queried, none) → still a real, gate-eligible observation.
            cpu_fired = None if wl_throttle is None else int(wl_throttle.get(name, 0))
            specs.append(("cpu", "millicores", _cpu_to_millicores(lim["cpu"]), peak["cpu"],
                          "throttle", cpu_fired))
        if not specs:
            unbounded.append(name)
            continue

        for resource, unit, limval, peakval, enforcement, fired in specs:
            # gate-eligible only if we actually measured a peak AND (for the verdict to mean
            # anything about teeth) the enforcement signal is known. CPU's fired is None -> the
            # peak is measured but the teeth question is unanswerable -> not gate-eligible.
            gate_eligible = bool(metrics_ok) and (fired is not None)
            verdict = expected_verdict(peak=peakval, limit=limval, fired_count=fired,
                                       gate_eligible=gate_eligible, enforcement=enforcement)
            tally[verdict] += 1
            contract = {
                "schemaVersion": "0.1.0", "kind": "ResourceContract",
                "contractId": f"{name}-{resource}",
                "resource": resource,  # 'memory' | 'cpu' — sourceos-spec ResourceContract enum members
                "limit": {"value": limval, "unit": unit},
                "window": f"PT{int(window_s)}S" if window_s else "PT0S",
                # scope=tenant needs no scopeRationale (that is required only for scope=process);
                # omit it rather than emit null, which fails the schema's type: string.
                "scope": "tenant",
                # An enforcing contract MUST carry a resolvable negative control (schema
                # INVARIANT). The producer observes; this procedure is how a workload's teeth
                # are proven, converting INCONCLUSIVE -> PROVED once run.
                "enforcement": enforcement,
                "negativeControl": "conformance/k8s-resource-enforcement-fires.md",
                "firedCount": fired if fired is not None else 0,
                "observedPeak": {
                    "schemaVersion": "0.1.0", "kind": "Measurement",
                    "label": f"{name} {resource} peak over {int(window_s)}s ({taken} samples)",
                    "value": round(peakval, 3),
                    "source": "measured" if metrics_ok else "assumed",
                    "instrument": "kubectl top (metrics-server)",
                    "sampling": {"observed": taken, "population": args.samples, "unit": "samples"},
                    "unobserved": 0,
                    "gateEligible": gate_eligible,
                },
            }
            contracts.append(contract)
            verdicts.append({
                "kind": "SufficiencyVerdict", "resource_contract_id": f"{name}-{resource}",
                "enforcement": enforcement, "fired_count": fired,
                "peak": round(peakval, 3), "limit": limval, "verdict": verdict,
                "reason": _reason(verdict, resource, name, peakval, limval, fired, enforcement, metrics_ok),
            })

    # ---- report ------------------------------------------------------------------
    print(f"ResourceContract producer — ns={ns}  {now}")
    print(f"  metrics-server: {'OK' if metrics_ok else 'UNREACHABLE'}  "
          f"({taken}/{args.samples} samples over ~{int(window_s)}s)")
    print(f"  workloads: {len(deploys)}   contracts emitted: {len(contracts)}   "
          f"UNBOUNDED (no limit → ungovernable): {len(unbounded)}")
    print(f"  verdicts: PROVED={tally['PROVED']}  VIOLATION={tally['VIOLATION']}  "
          f"INCONCLUSIVE={tally['INCONCLUSIVE']}")
    if unbounded:
        print(f"  🔴 no ResourceContract possible (no limit declared): {', '.join(sorted(unbounded))}")
    viol = [v for v in verdicts if v["verdict"] == "VIOLATION"]
    if viol:
        print("  🔴 VIOLATIONs (limit exceeded, enforcement never fired):")
        for v in viol:
            print(f"     {v['resource_contract_id']}: peak {v['peak']} > limit {v['limit']}")
    proved = [v for v in verdicts if v["verdict"] == "PROVED"]
    for v in proved:
        print(f"  ✓ PROVED {v['resource_contract_id']}: enforcement fired {v['fired_count']}x")

    if args.out:
        d = Path(args.out); d.mkdir(parents=True, exist_ok=True)
        (d / "resource-contracts.json").write_text(json.dumps(contracts, indent=2))
        (d / "sufficiency-verdicts.json").write_text(json.dumps(verdicts, indent=2))
        (d / "unbounded-workloads.json").write_text(json.dumps(sorted(unbounded), indent=2))
        print(f"  wrote {len(contracts)} contracts + {len(verdicts)} verdicts to {d}/")

    if args.publish_url and contracts:
        ok, failed = publish(args.publish_url, contracts)
        print(f"  published {ok}/{len(contracts)} contracts to the mesh ({failed} failed)")
    return 0


def _reason(verdict, resource, name, peak, limit, fired, enforcement, metrics_ok) -> str:
    if not metrics_ok:
        return "metrics-server unreachable — observed peak not measured, sufficiency unestablished"
    if resource == "cpu" and fired is None:
        return ("CPU throttle counter (cgroup cpu.stat nr_throttled) is not exposed via the k8s "
                "API, so whether the throttle enforcement fired is unknown — no teeth verdict "
                "can be drawn. Wire Prometheus/cAdvisor to make CPU contracts real.")
    if verdict == "PROVED":
        return f"{resource} limit enforced ({enforcement}) {fired}x on real load — the control has teeth"
    if verdict == "VIOLATION":
        return (f"{resource} peak {peak} exceeded limit {limit} yet enforcement never fired — a "
                "never-fired control (for memory this is anomalous: OOM should have fired)")
    return (f"{resource} peak {peak} stayed under limit {limit} and enforcement never needed to "
            "fire — the limit held, but its teeth are unproven (no breach observed)")


if __name__ == "__main__":
    sys.exit(main())
