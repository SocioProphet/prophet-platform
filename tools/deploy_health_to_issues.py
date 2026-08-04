#!/usr/bin/env python3
"""deploy_health_to_issues — route deploy-health findings to durable GitHub issues.

The deploy-health alerter (``deploy_health_alert.py``) detects live runtime gaps every
10 minutes, but until now its findings reached only two dead ends:

  * the Job's pod logs (ephemeral — gone on the next rotation), and
  * one *binary* Prometheus alert, ``DeployHealthGapsDetected``, that fires whenever
    ANY gap exists. Because the estate always carries some chronic gap, that alert is
    permanently firing and therefore ignored — so a NEW gap is invisible in the noise.

The 2026-08-04 workspace sync-trap is the receipt: three ArgoCD apps sat OutOfSync for
~40h while the alerter flagged them *every single cycle* into a void. Detection had
teeth; nothing consumed the bite. That is the detect≠heal gap this closes.

This reconciles the alerter's findings into GitHub issues, WITHOUT auto-mutating prod:

  * one open issue per (kind, workload) gap, de-duplicated (a crashlooping pod with two
    reasons is ONE issue, not two);
  * a chronic gap is a single standing issue — not re-fired noise;
  * a NEW gap opens a new issue immediately (it stands out because the others are old);
  * a gap that CLEARS closes its own issue (the control witnesses its own remediation).

Routing to issues — not to an auto-fixer — is deliberate: it makes every finding visible,
assignable and durable, and leaves the act to a human or an agent. Wiring the sociosphere
responder to *remediate* (law_by_kind) is the riskier next layer, tracked separately.

Honesty invariant (mirrors the alerter's own, and infra-drift-detect's exit-code map):
a BLIND report — exit 2 / could-not-observe (no cluster access, wrong context, API down) —
must NEVER close issues. "We couldn't look" is not "all clear"; closing on blind input
would silently resolve real, still-broken gaps. On blind input this refuses to reconcile
and exits non-zero, so the CI job goes RED instead of quietly marking everything fixed.

Pure reconciliation (``reconcile``) is I/O-free and self-tested (``--self-test`` / the
pytest beside it). GitHub I/O is a thin ``gh`` CLI layer, kept out of the tested core.

  deploy_health_alert.py --json | deploy_health_to_issues.py            # reconcile (writes)
  deploy_health_alert.py --json | deploy_health_to_issues.py --dry-run  # print the plan
  deploy_health_to_issues.py --self-test                                # prove it discriminates
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

# The label every issue this tool owns carries. Reconciliation is scoped to issues with
# this label: the tool must never touch an issue a human filed by hand, and must be able
# to enumerate exactly the set it is responsible for closing.
ISSUE_LABEL = "deploy-health"
TITLE_PREFIX = "[deploy-health]"

# Exit codes, aligned with deploy_health_alert.py: 0 clean, 1 reconciled-with-open-gaps,
# 2 blind (refused to reconcile — could-not-observe dominates, same fail-closed precedence).
EXIT_CLEAN, EXIT_ACTED, EXIT_BLIND = 0, 1, 2


# ── pure reconciliation (no I/O; this is what the self-test pins) ──────────────
def gap_key(kind: str, name: str) -> str:
    """Stable identity for a gap: the (kind, workload) pair, independent of the reason.

    Two findings on the same workload (e.g. a pod's ``CrashLoopBackOff`` and its
    ``restarts=10``) share a key so they collapse to ONE issue, not two.
    """
    return f"{kind}/{name}"


def title_for(key: str) -> str:
    """The issue title for a gap key — stable, so re-runs match the same issue."""
    return f"{TITLE_PREFIX} {key}"


def key_from_title(title: str) -> str | None:
    """Recover the gap key from an issue title, or None if it is not one of ours.

    Defensive: only titles with our exact prefix are treated as owned, so a human
    issue that merely contains 'deploy-health' in prose is never matched for closing.
    """
    if not title.startswith(TITLE_PREFIX + " "):
        return None
    return title[len(TITLE_PREFIX) + 1:].strip() or None


def group_findings(findings: list[dict]) -> dict[str, list[str]]:
    """Collapse the alerter's per-reason findings into {gap_key: [reasons...]}."""
    grouped: dict[str, list[str]] = {}
    for f in findings:
        key = gap_key(f.get("kind", "?"), f.get("name", "?"))
        grouped.setdefault(key, []).append(f.get("reason", ""))
    return grouped


def reconcile(
    findings: list[dict],
    open_issues: list[dict],
    *,
    blind: bool,
) -> dict:
    """Compute the issue actions for one scan. Pure: no network, no clock beyond caller's.

    Returns a plan ``{"blind": bool, "create": [{key,title,reasons}], "close": [{number,
    key,title}], "keep": [{number,key}]}``.

    * ``create`` — a current gap with no matching open issue.
    * ``close``  — an open issue we own whose gap is NOT in the current findings
                   (i.e. it cleared) — SUPPRESSED ENTIRELY when ``blind`` is True.
    * ``keep``   — a current gap that already has an open issue (left untouched — no spam).

    When ``blind`` is True we cannot prove any gap resolved, so nothing is closed and the
    caller is expected to fail loudly. New gaps could still be created, but a blind scan
    has no findings to create from, so in practice the plan is empty + blind.
    """
    grouped = group_findings(findings)
    owned_open: dict[str, dict] = {}
    for issue in open_issues:
        key = key_from_title(issue.get("title", ""))
        if key is not None:
            owned_open[key] = issue

    create = [
        {"key": key, "title": title_for(key), "reasons": reasons}
        for key, reasons in sorted(grouped.items())
        if key not in owned_open
    ]
    keep = [
        {"number": owned_open[key]["number"], "key": key}
        for key in sorted(grouped)
        if key in owned_open
    ]
    close: list[dict] = []
    if not blind:
        for key in sorted(owned_open):
            if key not in grouped:
                close.append({"number": owned_open[key]["number"],
                              "key": key, "title": owned_open[key].get("title", "")})
    return {"blind": blind, "create": create, "close": close, "keep": keep}


def issue_body(key: str, reasons: list[str], *, now_iso: str) -> str:
    """Render the issue body for a gap: what/why/how-to-clear, machine-greppable header."""
    kind, _, name = key.partition("/")
    reason_lines = "\n".join(f"- {r}" for r in reasons) or "- (no reason recorded)"
    return (
        f"**Live deploy-health gap** detected by `deploy_health_alert.py` and routed here "
        f"so it does not rot in a pod log.\n\n"
        f"- **kind:** `{kind}`\n"
        f"- **workload:** `{name}`\n"
        f"- **first surfaced:** {now_iso}\n\n"
        f"**Reason(s):**\n{reason_lines}\n\n"
        f"This issue is managed by `tools/deploy_health_to_issues.py`: it will **close "
        f"itself automatically** on the next scan in which the gap is gone. Do not close "
        f"it by hand to 'silence' a still-broken workload — fix the workload, or (for an "
        f"intentional state) declare a `socioprophet.io/deploy-health-hold` on the app.\n\n"
        f"Runbook: `infra/k8s/deploy-health-alerter/README.md`\n"
        f"<!-- deploy-health-key: {key} -->"
    )


# ── thin GitHub I/O via the gh CLI (kept out of the tested core) ───────────────
def _gh(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def ensure_label(repo: str) -> None:
    """Create the deploy-health label if missing (idempotent; --force won't error if it exists)."""
    _gh(["label", "create", ISSUE_LABEL, "--repo", repo, "--color", "B60205",
         "--description", "Live runtime gap routed by deploy_health_to_issues.py",
         "--force"], check=False)


def list_open_issues(repo: str) -> list[dict]:
    """Open issues carrying our label, as [{number, title}]."""
    r = _gh(["issue", "list", "--repo", repo, "--label", ISSUE_LABEL, "--state", "open",
             "--limit", "500", "--json", "number,title"])
    return json.loads(r.stdout or "[]")


def apply_plan(plan: dict, repo: str, *, now_iso: str) -> None:
    """Execute a reconcile plan against GitHub. Never called on blind input."""
    for item in plan["create"]:
        body = issue_body(item["key"], item["reasons"], now_iso=now_iso)
        _gh(["issue", "create", "--repo", repo, "--title", item["title"],
             "--label", ISSUE_LABEL, "--body", body])
        print(f"  opened: {item['title']}")
    for item in plan["close"]:
        _gh(["issue", "close", str(item["number"]), "--repo", repo, "--reason", "completed",
             "--comment", f"Resolved: no longer detected by deploy-health at {now_iso}. "
                          f"Auto-closed by deploy_health_to_issues.py."])
        print(f"  closed #{item['number']}: {item['title']}")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── negative control: prove the reconciler discriminates ──────────────────────
def _self_test() -> int:
    F = [{"kind": "argocd-app", "name": "ws-workspace-caldav", "reason": "sync=OutOfSync (sync failing)"}]
    POD2 = [
        {"kind": "pod", "name": "sherlock-x", "reason": "svc:CrashLoopBackOff"},
        {"kind": "pod", "name": "sherlock-x", "reason": "svc:restarts=10"},
    ]
    ISSUE = {"number": 42, "title": "[deploy-health] argocd-app/ws-workspace-caldav"}
    OTHER = {"number": 7, "title": "[deploy-health] pod/gone-away"}
    HUMAN = {"number": 9, "title": "investigate deploy-health flakiness"}  # not ours

    checks = [
        ("new gap → create",
         [c["key"] for c in reconcile(F, [], blind=False)["create"]] == ["argocd-app/ws-workspace-caldav"]),
        ("existing gap → keep, not re-create",
         reconcile(F, [ISSUE], blind=False)["create"] == []
         and [k["number"] for k in reconcile(F, [ISSUE], blind=False)["keep"]] == [42]),
        ("cleared gap → close",
         [c["number"] for c in reconcile([], [ISSUE], blind=False)["close"]] == [42]),
        ("two reasons, one workload → ONE issue",
         len(reconcile(POD2, [], blind=False)["create"]) == 1
         and len(reconcile(POD2, [], blind=False)["create"][0]["reasons"]) == 2),
        ("blind scan NEVER closes (could-not-observe ≠ all-clear)",
         reconcile([], [ISSUE, OTHER], blind=True)["close"] == []),
        ("human-filed issue is never closed by us",
         reconcile([], [HUMAN], blind=False)["close"] == []),
        ("mixed: one clears, one persists",
         sorted(c["number"] for c in reconcile(F, [ISSUE, OTHER], blind=False)["close"]) == [7]
         and [k["number"] for k in reconcile(F, [ISSUE, OTHER], blind=False)["keep"]] == [42]),
        ("title round-trips to key",
         key_from_title(title_for("pod/foo")) == "pod/foo"),
        ("non-owned title → no key",
         key_from_title("investigate deploy-health") is None),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗ FAIL'} {name}")
    if failed:
        print(f"self-test FAILED: {failed}")
        return 1
    print(f"self-test OK ({len(checks)} reconciliation checks)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Route deploy-health findings to GitHub issues (fail-closed).")
    p.add_argument("--report", help="deploy-health --json report file (default: stdin)")
    p.add_argument("--repo", default="SocioProphet/prophet-platform", help="owner/repo for issues")
    p.add_argument("--dry-run", action="store_true", help="print the plan; make no changes")
    p.add_argument("--self-test", action="store_true", help="run the reconciliation checks and exit")
    args = p.parse_args(argv)

    if args.self_test:
        return _self_test()

    raw = open(args.report, encoding="utf-8").read() if args.report else sys.stdin.read()
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[to-issues] report is not JSON: {e}\n")
        return EXIT_BLIND  # could not even read the scan → treat as blind, never as clean

    findings = report.get("findings") or []
    # Blind = the alerter told us it could not observe something (exit 2 or a non-empty blind list).
    blind = int(report.get("exit", 0)) == EXIT_BLIND or bool(report.get("blind"))
    now_iso = _utc_iso()

    if args.dry_run:
        # No network at all in dry-run: reconcile against an EMPTY open-issue set so the plan
        # is derivable offline (self-test covers the open-issue matching logic).
        plan = reconcile(findings, [], blind=blind)
        print(json.dumps({"now": now_iso, **plan}, indent=2))
        return EXIT_BLIND if blind else (EXIT_ACTED if findings else EXIT_CLEAN)

    if blind:
        # Fail-closed: refuse to reconcile, so no issue is wrongly closed and CI goes red.
        sys.stderr.write(
            "[to-issues] BLIND report (could-not-observe) — refusing to reconcile: "
            "not closing any issue, exiting non-zero.\n")
        return EXIT_BLIND

    ensure_label(args.repo)
    open_issues = list_open_issues(args.repo)
    plan = reconcile(findings, open_issues, blind=False)
    print(f"deploy-health → issues @ {now_iso}: "
          f"{len(plan['create'])} to open, {len(plan['close'])} to close, "
          f"{len(plan['keep'])} unchanged")
    apply_plan(plan, args.repo, now_iso=now_iso)
    return EXIT_ACTED if (plan["create"] or plan["keep"]) else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
