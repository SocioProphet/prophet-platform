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
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _kubectl(args: list[str]) -> str:
    return subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=60).stdout


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
    """MAX cpu(millicores)/mem(bytes) per pod over `samples` reads. Returns (peaks, taken)."""
    peaks: dict[str, dict[str, float]] = {}
    taken = 0
    for i in range(samples):
        out = _kubectl(["top", "pods", "-n", ns, "--no-headers"])
        if not out.strip():
            continue
        taken += 1
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            pod, cpu, mem = parts[0], _cpu_to_millicores(parts[1]), _mem_to_bytes(parts[2])
            d = peaks.setdefault(pod, {"cpu": 0.0, "mem": 0.0})
            if cpu is not None:
                d["cpu"] = max(d["cpu"], cpu)
            if mem is not None:
                d["mem"] = max(d["mem"], mem)
        if i < samples - 1:
            time.sleep(interval)
    return peaks, taken


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", default="socioprophet")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--interval", type=float, default=8.0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    ns = args.namespace

    deploys_raw = _kubectl(["get", "deploy", "-n", ns, "-o", "json"])
    if not deploys_raw.strip():
        print("kubectl unreachable or no deployments — everything INCONCLUSIVE", file=sys.stderr)
        return 2
    deploys = json.loads(deploys_raw)["items"]

    window_s = args.interval * max(args.samples - 1, 0)
    peaks, taken = sample_peaks(ns, args.samples, args.interval)
    metrics_ok = taken > 0

    # OOMKilled count per workload (memory enforcement FIRED), from pod lastState.
    pods = json.loads(_kubectl(["get", "pods", "-n", ns, "-o", "json"]) or '{"items":[]}')["items"]
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
            specs.append(("cpu", "millicores", _cpu_to_millicores(lim["cpu"]), peak["cpu"],
                          "throttle", None))                       # throttle counter not collected
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
