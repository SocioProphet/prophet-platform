#!/usr/bin/env python3
"""deploy_health_alert — alert on the *gap*, not the event.

Every static deploy gate in this repo (`preflight_deploy_contract.py`,
`verify_pinned_digest_exists.py`, …) inspects YAML and registries *before* a
rollout. They all stayed green while `arcticdb-gateway` ran broken for ~20h in
`CreateContainerConfigError` (a missing secret): its values file was valid, its
digest existed — the defect lived only in the *running* state, which nothing
watched. A control that cannot observe the failure it exists to catch is the
paper control this estate keeps refusing.

This tool closes that gap. It reads live runtime state and FAILS (non-zero) on
any condition that would otherwise sit unnoticed:

  * ArgoCD applications that are Degraded / Missing / Unknown, or OutOfSync.
  * Pods stuck in a waiting reason (CrashLoopBackOff, CreateContainerConfigError,
    ImagePullBackOff, …) or restarting above a threshold.
  * Job receipts (see --receipts) that are STALE (a scheduled job silently
    stopped running) or record a non-zero exit (it ran but failed) or are
    MISSING (it never ran at all) — the generalized form of the backup that
    exited 0 for days while every night's copy failed.

Two honesty invariants, both self-tested (`--self-test` / the pytest beside it):

  1. The classifier must DISCRIMINATE. A synthetic Degraded app / stuck pod /
     stale receipt must be flagged; a healthy one must not. A gate that cannot
     fire is worthless.
  2. An empty scan is NOT "all clear." If we asked to scan apps or pods and
     kubectl returned nothing (no access, wrong context, API down), we exit 2
     (could-not-observe), never 0. Absence of observed failure is not evidence
     of health — the instruments-lie lesson, made executable.

An app may DECLARE a deliberate audit-first hold (see HOLD_ANNOTATION) so this
tool does not cry wolf on a Missing/OutOfSync-by-design rollout (e.g. the kyverno
controller, whose sync flips Enforce policies estate-wide). The hold is accountable,
not a mute: it must carry a reason, and it never excuses a Degraded app.

Stdlib only. Read-only against the cluster (get/list); it never mutates. Runs
either locally via kubectl or as an in-cluster CronJob talking to the API server
directly over the mounted ServiceAccount token (auto-detected — no kubectl needed
in the pod); see infra/k8s/deploy-health-alerter/.

  deploy_health_alert.py --namespace socioprophet          # pods + argocd apps
  deploy_health_alert.py --receipts ~/.local/state/receipts # + job-receipt staleness
  deploy_health_alert.py --json                             # machine-readable findings
  deploy_health_alert.py --self-test                        # prove the classifier has teeth
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── what counts as a gap (the vocabulary the classifier discriminates on) ─────
# Pod container waiting-reasons that mean "stuck", not "starting". These are the
# reasons that do not clear on their own — the arcticdb-gateway class of defect.
STUCK_WAITING = frozenset({
    "CrashLoopBackOff", "CreateContainerConfigError", "CreateContainerError",
    "ImagePullBackOff", "ErrImagePull", "InvalidImageName", "RunContainerError",
    "ImageInspectError", "ErrImageNeverPull",
})
# ArgoCD Application health states that are not "the desired state is running".
UNHEALTHY_APP_HEALTH = frozenset({"Degraded", "Missing", "Unknown"})

# An app may DECLARE a deliberate hold — an audit-first / staged rollout that is
# Missing/OutOfSync *on purpose* (e.g. the kyverno controller: syncing it flips
# Enforce ClusterPolicies estate-wide, so it waits for a deliberate operator sync).
# The alerter must not cry wolf on such an app, or the whole control gets ignored.
# But the hold is accountable, not a mute button:
#   * it MUST carry a non-empty reason (a hold with no justification is itself a gap);
#   * it excuses only "declared but not yet synced" (Missing health, OutOfSync) —
#     never Degraded/Unknown (you may hold a rollout, not declare a broken thing "held").
HOLD_ANNOTATION = "socioprophet.io/deploy-health-hold"
# The states a valid hold is allowed to suppress (and only these).
HOLD_SUPPRESSES_HEALTH = frozenset({"Missing"})

# Exit codes: 0 clean, 1 gaps found, 2 could-not-observe (fail-closed).
EXIT_CLEAN, EXIT_GAPS, EXIT_BLIND = 0, 1, 2


# ── pure classification (no I/O; this is what the negative control pins) ──────
def app_hold_reason(app: dict) -> str | None:
    """The declared hold reason for an app, or None if it declares no hold.

    Returns "" (falsy but not None) when the hold annotation is present but empty —
    a hold without justification, which the classifier treats as a gap.
    """
    ann = ((app.get("metadata") or {}).get("annotations")) or {}
    return ann.get(HOLD_ANNOTATION)


def classify_app(app: dict, *, ignore_sync: bool = False) -> list[str]:
    """Return the list of gap reasons for one ArgoCD Application (empty = healthy).

    Honors a declared, justified hold (see HOLD_ANNOTATION): a held app's expected
    Missing/OutOfSync states are suppressed, but Degraded/Unknown and an
    unjustified hold still fire.
    """
    status = app.get("status") or {}
    reasons: list[str] = []
    hold = app_hold_reason(app)
    justified_hold = bool((hold or "").strip())
    if hold is not None and not justified_hold:
        # declared a hold but gave no reason — accountability failure, always a gap
        reasons.append("held-without-reason (a hold must carry a justification)")
    health = ((status.get("health") or {}).get("status")) or "Unknown"
    if health in UNHEALTHY_APP_HEALTH:
        if not (justified_hold and health in HOLD_SUPPRESSES_HEALTH):
            reasons.append(f"health={health}")
    sync = ((status.get("sync") or {}).get("status")) or ""
    if sync == "OutOfSync" and not ignore_sync and not justified_hold:
        # OutOfSync alone is NOT a gap: on an auto-sync+selfHeal estate a Healthy app is
        # routinely OutOfSync for a moment mid-reconcile, and flagging that trains people to
        # ignore the alerter. It IS a gap only when ArgoCD recorded a sync FAILURE (objects
        # failed to apply) — real drift self-heal cannot resolve. An unhealthy app is already
        # reported via its health above, so OutOfSync adds nothing there.
        if _sync_failing(status):
            reasons.append("sync=OutOfSync (sync failing)")
    return reasons


def _sync_failing(status: dict) -> bool:
    """True if ArgoCD recorded a sync error/failure condition (not a transient OutOfSync)."""
    for cond in (status.get("conditions") or []):
        ctype = (cond.get("type") or "").lower()
        msg = (cond.get("message") or "").lower()
        if "error" in ctype or "failed sync" in msg or "failed to apply" in msg:
            return True
    return False


def classify_pod(pod: dict, *, restart_threshold: int) -> list[str]:
    """Return the list of gap reasons for one Pod (empty = healthy / benign)."""
    meta = pod.get("metadata") or {}
    status = pod.get("status") or {}
    # A pod being torn down or already finished is not a gap.
    if meta.get("deletionTimestamp"):
        return []
    if (status.get("phase") or "") in ("Succeeded", "Completed"):
        return []
    reasons: list[str] = []
    for cs in (status.get("containerStatuses") or []):
        name = cs.get("name", "?")
        waiting = ((cs.get("state") or {}).get("waiting")) or {}
        reason = waiting.get("reason")
        if reason in STUCK_WAITING:
            reasons.append(f"{name}:{reason}")
        restarts = int(cs.get("restartCount", 0) or 0)
        if restarts >= restart_threshold:
            reasons.append(f"{name}:restarts={restarts}")
    return reasons


def _to_epoch(ts: Any) -> float | None:
    """Accept a receipt timestamp as epoch seconds (int/float/str) or ISO-8601."""
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str) and ts.strip():
        s = ts.strip()
        try:
            return float(s)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def classify_receipt(receipt: dict | None, *, now_epoch: float, max_age_s: int) -> list[str]:
    """Return gap reasons for one job receipt.

    A receipt is ``{"job": str, "ts": <epoch|iso>, "rc": int}`` written by a job
    at completion. ``None`` means the expected receipt is absent — the strongest
    silent failure (the job never ran, so it never got the chance to report red).
    """
    if receipt is None:
        return ["missing (job wrote no receipt — did it run at all?)"]
    reasons: list[str] = []
    epoch = _to_epoch(receipt.get("ts"))
    if epoch is None:
        reasons.append("unparseable/absent ts")
    else:
        age = now_epoch - epoch
        if age > max_age_s:
            reasons.append(f"stale ({int(age)}s old > max {max_age_s}s)")
    rc = receipt.get("rc")
    if rc is None:
        reasons.append("no rc recorded")
    elif int(rc) != 0:
        reasons.append(f"rc={rc}")
    return reasons


# ── I/O (kubectl + filesystem); kept thin so classification stays pure ────────
def _kubectl_json(args: list[str]) -> dict | None:
    """Run a read-only kubectl command and parse JSON; None on any failure."""
    try:
        r = subprocess.run(["kubectl", *args, "-o", "json"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        sys.stderr.write(f"[deploy-health] kubectl {' '.join(args)} errored: {e}\n")
        return None
    if r.returncode != 0:
        sys.stderr.write(f"[deploy-health] kubectl {' '.join(args)} rc={r.returncode}: "
                         f"{r.stderr.strip()[:300]}\n")
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(f"[deploy-health] kubectl {' '.join(args)} returned non-JSON\n")
        return None


# ── in-cluster Kubernetes API (no kubectl) ───────────────────────────────────
# When this runs as an in-cluster CronJob there is no kubectl binary — it reads
# the mounted ServiceAccount token and talks to the API server directly over
# stdlib urllib, the same pattern as infra/k8s/pvc-capacity-guard/base/guard.py.
# That keeps the workload on a bare, digest-pinned python image with no kubectl
# layer to vendor or patch.
_SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"


def in_cluster() -> bool:
    """True when running inside the cluster with a usable ServiceAccount."""
    return bool(os.environ.get("KUBERNETES_SERVICE_HOST")) and os.path.isfile(f"{_SA_DIR}/token")


def _api_get(path: str) -> dict | None:
    """GET a JSON document from the in-cluster API server; None on any failure."""
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
        sys.stderr.write(f"[deploy-health] in-cluster GET {path} failed: {e}\n")
        return None


def collect_apps(argocd_ns: str) -> list[dict] | None:
    """List ArgoCD Applications — in-cluster REST when available, else kubectl."""
    if in_cluster():
        out = _api_get(f"/apis/argoproj.io/v1alpha1/namespaces/{argocd_ns}/applications")
    else:
        out = _kubectl_json(["-n", argocd_ns, "get", "applications"])
    return None if out is None else (out.get("items") or [])


def collect_pods(namespace: str) -> list[dict] | None:
    """List Pods — in-cluster REST when available, else kubectl."""
    if in_cluster():
        out = _api_get(f"/api/v1/namespaces/{namespace}/pods")
    else:
        out = _kubectl_json(["-n", namespace, "get", "pods"])
    return None if out is None else (out.get("items") or [])


def load_receipts(directory: Path) -> dict[str, dict | None]:
    """Load every ``*.json`` receipt in a directory, keyed by job name.

    A file that is present but malformed is surfaced as a distinct gap rather
    than silently skipped — a corrupt receipt is itself a failed report.
    """
    receipts: dict[str, dict | None] = {}
    if not directory.is_dir():
        return receipts
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            name = str(data.get("job") or path.stem)
            receipts[name] = data
        except (json.JSONDecodeError, OSError):
            receipts[path.stem] = {"job": path.stem, "ts": None, "rc": "unreadable"}
    return receipts


# ── orchestration ─────────────────────────────────────────────────────────────
def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── self-heal bridge: turn findings into beacons the sociosphere responder consumes ──
# The reasoned self-heal responder (sociosphere automation/responder.py) decides on "beacons"
# keyed by kind_class → its law_by_kind → an action (auto_fix / canary_fix / propose_pr / …).
# This maps each deploy-health finding to a kind_class so detection can DRIVE remediation, not
# just alert. The sociosphere side must add these classes to law_by_kind + register executors
# (see the P1.5 integration issue) — until then the responder fail-closes them to `refuse`.
def _beacon_kind_class(finding: dict) -> str:
    reason = finding.get("reason", "")
    if finding.get("kind") == "pod":
        if "CreateContainerConfigError" in reason or "CreateContainerError" in reason:
            return "missing_config"           # e.g. the arcticdb-gateway missing-secret class
        if "ImagePull" in reason or "ErrImage" in reason or "InvalidImageName" in reason:
            return "image_pull_failure"
        if "CrashLoopBackOff" in reason or "restarts=" in reason:
            return "crashloop"
        return "pod_stuck"
    if finding.get("kind") == "argocd-app":
        if "health=Degraded" in reason:
            return "app_degraded"
        if "health=Missing" in reason:
            return "app_missing"
        if "health=Unknown" in reason:
            return "app_unknown"
        if "sync=OutOfSync" in reason:
            return "sync_failure"
        if "held-without-reason" in reason:
            return "unaccountable_hold"
    if finding.get("kind") == "job-receipt":
        return "job_receipt_stale"
    return "unknown"


def beacon_of(finding: dict) -> dict:
    """A responder beacon for one finding: kind_class (routes the Law) + system + evidence."""
    return {
        "kind_class": _beacon_kind_class(finding),
        "system": finding.get("name", "?"),
        "detail": finding.get("reason", ""),
        "source": "deploy-health-alerter",
        "ts": time.time(),
    }


def run(args: argparse.Namespace) -> tuple[int, dict]:
    """Return (exit_code, report). Pure-ish: all I/O is behind collect_*/load_*."""
    findings: list[dict] = []
    held: list[dict] = []  # apps suppressed by a declared, justified hold (informational)
    scanned = {"apps": 0, "pods": 0, "receipts": 0}
    blind: list[str] = []  # things we were asked to observe but could not

    if not args.no_argocd:
        apps = collect_apps(args.argocd_namespace)
        if apps is None:
            blind.append(f"argocd applications in ns/{args.argocd_namespace}")
        else:
            scanned["apps"] = len(apps)
            if not apps:
                blind.append(f"argocd applications in ns/{args.argocd_namespace} (zero found)")
            for app in apps:
                name = (app.get("metadata") or {}).get("name", "?")
                reasons = classify_app(app, ignore_sync=args.ignore_sync)
                for reason in reasons:
                    findings.append({"kind": "argocd-app", "name": name, "reason": reason})
                # A justified hold that produced no gap is reported (never silently
                # suppressed — a mute control is the defect this tool exists to catch).
                hold = app_hold_reason(app)
                if hold and (hold or "").strip() and not reasons:
                    held.append({"name": name, "reason": hold.strip()})

    if not args.no_pods:
        pods = collect_pods(args.namespace)
        if pods is None:
            blind.append(f"pods in ns/{args.namespace}")
        else:
            scanned["pods"] = len(pods)
            if not pods:
                blind.append(f"pods in ns/{args.namespace} (zero found)")
            for pod in pods:
                name = (pod.get("metadata") or {}).get("name", "?")
                for reason in classify_pod(pod, restart_threshold=args.restart_threshold):
                    findings.append({"kind": "pod", "name": name, "reason": reason})

    if args.receipts:
        directory = Path(args.receipts).expanduser()
        receipts = load_receipts(directory)
        scanned["receipts"] = len(receipts)
        expected = [e for e in (args.expect or []) if e]
        # expected-but-absent receipts are the strongest signal: the job never ran.
        for name in expected:
            if name not in receipts:
                receipts[name] = None
        if not receipts:
            blind.append(f"job receipts in {directory}")
        now_epoch = time.time()
        for name, receipt in sorted(receipts.items()):
            for reason in classify_receipt(receipt, now_epoch=now_epoch,
                                           max_age_s=args.max_receipt_age):
                findings.append({"kind": "job-receipt", "name": name, "reason": reason})

    # Fail-closed precedence: could-not-observe (2) dominates gaps-found (1).
    if blind and not args.allow_blind:
        code = EXIT_BLIND
    elif findings:
        code = EXIT_GAPS
    else:
        code = EXIT_CLEAN
    report = {"generatedAt": _utc(), "scanned": scanned, "blind": blind,
              "gapCount": len(findings), "findings": findings, "held": held, "exit": code}
    return code, report


def _print_human(report: dict) -> None:
    s = report["scanned"]
    print(f"deploy-health @ {report['generatedAt']}")
    print(f"  scanned: {s['apps']} argocd-apps, {s['pods']} pods, {s['receipts']} receipts")
    if report["blind"]:
        print(f"  ⚠ COULD NOT OBSERVE ({len(report['blind'])}) — absence of failure ≠ health:")
        for b in report["blind"]:
            print(f"      · {b}")
    for h in report.get("held", []):
        print(f"  ⏸ HELD (declared, not a gap) {h['name']}: {h['reason']}")
    if not report["findings"]:
        if not report["blind"]:
            print("  ✓ no runtime gaps found in what was scanned")
        return
    print(f"  ✗ {report['gapCount']} gap(s):")
    for f in report["findings"]:
        print(f"      [{f['kind']}] {f['name']}: {f['reason']}")


# ── negative control: prove the classifier discriminates (embedded self-test) ─
def _self_test() -> int:
    now = 1_000_000.0
    checks = [
        ("healthy app clean",
         classify_app({"status": {"health": {"status": "Healthy"}, "sync": {"status": "Synced"}}}) == []),
        ("degraded app flagged",
         classify_app({"status": {"health": {"status": "Degraded"}, "sync": {"status": "Synced"}}}) == ["health=Degraded"]),
        ("bare outofsync (healthy, no error) is NOT a gap",
         classify_app({"status": {"health": {"status": "Healthy"}, "sync": {"status": "OutOfSync"}}}) == []),
        ("outofsync WITH a sync failure IS a gap",
         any("sync=OutOfSync" in r for r in classify_app({"status": {"health": {"status": "Healthy"},
             "sync": {"status": "OutOfSync"}, "conditions": [{"message": "one or more objects failed to apply"}]}}))),
        ("failing-sync outofsync ignorable",
         classify_app({"status": {"health": {"status": "Healthy"}, "sync": {"status": "OutOfSync"},
             "conditions": [{"message": "failed to apply"}]}}, ignore_sync=True) == []),
        ("justified hold suppresses missing+outofsync",
         classify_app({"metadata": {"annotations": {HOLD_ANNOTATION: "audit-first, see ROLLOUT.md"}},
                       "status": {"health": {"status": "Missing"}, "sync": {"status": "OutOfSync"}}}) == []),
        ("hold does NOT excuse degraded",
         classify_app({"metadata": {"annotations": {HOLD_ANNOTATION: "audit-first"}},
                       "status": {"health": {"status": "Degraded"}, "sync": {"status": "OutOfSync"}}}) == ["health=Degraded"]),
        ("hold without reason is itself a gap",
         any("held-without-reason" in r for r in classify_app(
             {"metadata": {"annotations": {HOLD_ANNOTATION: "  "}},
              "status": {"health": {"status": "Missing"}, "sync": {"status": "OutOfSync"}}}))),
        ("running pod clean",
         classify_pod({"status": {"phase": "Running", "containerStatuses": [
             {"name": "c", "state": {"running": {}}, "restartCount": 0}]}}, restart_threshold=5) == []),
        ("stuck pod flagged",
         classify_pod({"status": {"phase": "Pending", "containerStatuses": [
             {"name": "c", "state": {"waiting": {"reason": "CreateContainerConfigError"}}, "restartCount": 0}]}},
             restart_threshold=5) == ["c:CreateContainerConfigError"]),
        ("high restarts flagged",
         classify_pod({"status": {"phase": "Running", "containerStatuses": [
             {"name": "c", "state": {"running": {}}, "restartCount": 9}]}}, restart_threshold=5) == ["c:restarts=9"]),
        ("terminating pod ignored",
         classify_pod({"metadata": {"deletionTimestamp": "now"}, "status": {"phase": "Running",
             "containerStatuses": [{"name": "c", "state": {"waiting": {"reason": "CrashLoopBackOff"}}}]}},
             restart_threshold=5) == []),
        ("succeeded job pod ignored",
         classify_pod({"status": {"phase": "Succeeded", "containerStatuses": [
             {"name": "c", "state": {"terminated": {"reason": "Completed"}}, "restartCount": 0}]}},
             restart_threshold=5) == []),
        ("fresh rc0 receipt clean",
         classify_receipt({"job": "b", "ts": now - 10, "rc": 0}, now_epoch=now, max_age_s=3600) == []),
        ("stale receipt flagged",
         any("stale" in r for r in classify_receipt({"job": "b", "ts": now - 99999, "rc": 0},
                                                     now_epoch=now, max_age_s=3600))),
        ("failed receipt flagged",
         "rc=1" in classify_receipt({"job": "b", "ts": now - 10, "rc": 1}, now_epoch=now, max_age_s=3600)),
        ("missing receipt flagged",
         classify_receipt(None, now_epoch=now, max_age_s=3600) != []),
        ("iso ts parses",
         classify_receipt({"job": "b", "ts": datetime.fromtimestamp(now - 10, timezone.utc).isoformat(),
                           "rc": 0}, now_epoch=now, max_age_s=3600) == []),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗ FAIL'} {name}")
    if failed:
        print(f"self-test FAILED: {failed}")
        return 1
    print(f"self-test OK ({len(checks)} discrimination checks)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Alert on live deploy-health gaps (fail-closed).")
    p.add_argument("--namespace", default="socioprophet", help="pod namespace to scan")
    p.add_argument("--argocd-namespace", default="argocd", help="ArgoCD Application namespace")
    p.add_argument("--no-pods", action="store_true", help="skip the pod scan")
    p.add_argument("--no-argocd", action="store_true", help="skip the ArgoCD app scan")
    p.add_argument("--ignore-sync", action="store_true", help="do not treat OutOfSync as a gap")
    p.add_argument("--restart-threshold", type=int, default=8,
                   help="restartCount at/above which a container is a gap")
    p.add_argument("--receipts", help="directory of job-receipt *.json files to check for staleness")
    p.add_argument("--expect", action="append", default=[],
                   help="a job name that MUST have a receipt (repeatable); absent ⇒ gap")
    p.add_argument("--max-receipt-age", type=int, default=93600,
                   help="max receipt age in seconds before stale (default 26h)")
    p.add_argument("--allow-blind", action="store_true",
                   help="do NOT fail when a scan observes nothing (default: fail-closed)")
    p.add_argument("--json", action="store_true", help="emit the report as JSON")
    p.add_argument("--emit-beacons", metavar="DIR",
                   help="also write each finding as a self-heal beacon (kind_class + system) to "
                        "DIR, for the sociosphere responder to decide on (detection → remediation)")
    p.add_argument("--self-test", action="store_true",
                   help="run the classifier discrimination checks and exit")
    args = p.parse_args(argv)

    if args.self_test:
        return _self_test()

    code, report = run(args)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    if args.emit_beacons and report["findings"]:
        d = Path(args.emit_beacons).expanduser()
        d.mkdir(parents=True, exist_ok=True)

        def _safe(s: str) -> str:
            # keep the filename inside DIR: no '/', '..', or odd chars can steer the write path.
            # k8s names are already DNS-safe, but a finding name is data — sanitize defensively.
            return "".join(c if (c.isalnum() or c in "._-") else "_" for c in str(s))[:120] or "x"

        for i, f in enumerate(report["findings"]):
            b = beacon_of(f)
            (d / f"{_safe(b['kind_class'])}-{_safe(b['system'])}-{i}.json").write_text(json.dumps(b) + "\n")
        print(f"  emitted {len(report['findings'])} self-heal beacon(s) to {d}")
    return code


if __name__ == "__main__":
    sys.exit(main())
