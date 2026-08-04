#!/usr/bin/env python3
"""CI liveness — the dead-man's switch for the estate's pipelines.

`controls_census.py` already names the property this enforces: *meta-monitored — something alerts
if the control itself stops (the check checks the checker)*. It applies that to in-cluster CronJobs
and to the `tools/` validators wired into `make validate`. It does not look at the CI workflows
themselves, and that is exactly where the estate lost five weeks.

**The case this exists for.** `SourceOS-Linux/goose-notes` CI reported `startup_failure` in 0s on
every branch from 2026-07-01 to 2026-08-04 — a disallowed action in the workflow meant GitHub
refused to start the run at all. `main` did not compile for five weeks and nothing said so, because:

    a red build is information.
    A BUILD THAT NEVER RUNS PRODUCES THE SAME OBSERVABLE AS A PASSING BUILD: no reported failures.

No alerting rule fires on that. No self-healing loop triggers on it either — healing is downstream
of detection, and this class of failure kills detection itself. You cannot heal what was never
observed to be sick.

**So this inverts the polarity.** It does not wait for red. It requires *green, recently*:

    for every repo, for every workflow — when did it last COMPLETE SUCCESSFULLY?

Staleness becomes the alarm, which makes silence a positive signal instead of a null one. That is
the same shape as the rest of the estate's fail-closed controls: absence of a marker is not
permission, an undecidable invariant is not a pass, unstated authority is not independence — and
here, **no news is not good news**.

Three verdicts, and the middle one is the one that was invisible:

    DEAD   never completed successfully, ever. The pipeline has never worked.
    SILENT ran recently but has not SUCCEEDED inside the window — includes the goose-notes
           signature, where runs exist and all of them are `startup_failure` at 0s.
    STALE  succeeded once, but not inside the window. Either abandoned or quietly broken.

Self-excluding by construction: this sweep reads the GitHub API and asserts nothing about itself.
Whatever schedules it must be watched by something else — the recursion has to bottom out in
something trusted by construction rather than by monitoring, or you have merely added one more
daemon that can die quietly. See `docs/CI_LIVENESS.md`.

stdlib + `gh`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_WINDOW_DAYS = 14

OK, STALE, SILENT, DEAD, UNUSED = "OK", "STALE", "SILENT", "DEAD", "UNUSED"
# UNUSED is deliberately NOT an alarm. A dispatch-only workflow nobody has invoked is not broken,
# and a checker that cries wolf gets muted — which makes it exactly the dead control it was built
# to find. Precision here is what keeps the signal worth reading.
ALARM_VERDICTS = (STALE, SILENT, DEAD)


class SweepError(RuntimeError):
    pass


def _gh(args: list[str]) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SweepError(f"gh {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def list_workflows(repo: str) -> list[dict]:
    """Active workflows for a repo. A disabled workflow is not a liveness concern."""
    out = _gh(["api", f"repos/{repo}/actions/workflows", "--paginate",
               "--jq", ".workflows[] | {id, name, state, path}"])
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def last_success(repo: str, workflow_id: int) -> str | None:
    """ISO timestamp of the most recent SUCCESSFUL completion, or None if there has never been one."""
    out = _gh(["api",
               f"repos/{repo}/actions/workflows/{workflow_id}/runs?status=success&per_page=1",
               "--jq", ".workflow_runs[0].updated_at // empty"]).strip()
    return out or None


AUTO_TRIGGERS = ("push", "pull_request", "schedule", "release", "pull_request_target",
                 "merge_group", "workflow_call")


def is_dispatch_only(repo: str, path: str) -> bool:
    """True when a workflow's only triggers are manual. Such a workflow not having run is a fact
    about usage, not about health — and calling it DEAD would train people to ignore this tool."""
    try:
        content = _gh(["api", f"repos/{repo}/contents/{path}", "--jq", ".content"])
    except SweepError:
        return False   # fail closed: if we cannot read it, do not grant it the benign verdict
    import base64
    try:
        text = base64.b64decode(content).decode("utf-8", "replace")
    except Exception:
        return False
    head = text.split("jobs:", 1)[0]
    return ("dispatch" in head) and not any(f"{t}:" in head for t in AUTO_TRIGGERS)


def last_run(repo: str, workflow_id: int) -> dict | None:
    """The most recent run of any conclusion — used to tell DEAD from SILENT."""
    out = _gh(["api", f"repos/{repo}/actions/workflows/{workflow_id}/runs?per_page=1",
               # `// empty` MUST bind before the object is constructed: `{a,b} // empty` builds
               # {a:null,b:null} from a null run — a truthy object — so "no runs at all" would be
               # misreported as "a run with no conclusion". Filter the null FIRST.
               "--jq", ".workflow_runs[0] // empty | {conclusion, updated_at}"]).strip()
    if not out:
        return None
    latest = json.loads(out)
    # a run row without a timestamp is not a run we can reason about
    return latest if latest.get("updated_at") else None


def classify(success_at: str | None, latest: dict | None, *, window_days: int,
             now: datetime | None = None, dispatch_only: bool = False) -> tuple[str, str]:
    """Return (verdict, why). The polarity is deliberate: we require green RECENTLY.

    `dispatch_only` marks a workflow whose only trigger is `workflow_dispatch` (or
    `repository_dispatch`). Those do not run on their own, so "never ran" means "never invoked",
    which is a fact about usage rather than about health.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    if success_at is None:
        if latest is None:
            if dispatch_only:
                return UNUSED, "manual-dispatch workflow that has never been invoked — unused, not broken"
            return DEAD, "no runs at all — the workflow has never executed"
        concl = latest.get("conclusion")
        if concl is None:
            return UNUSED, "most recent run is still in progress and there is no prior success yet"
        return DEAD, (f"never completed successfully; most recent run concluded {concl!r} — "
                      "a pipeline that has never worked")

    succeeded = datetime.fromisoformat(success_at.replace("Z", "+00:00"))
    if succeeded >= cutoff:
        return OK, f"last green {succeeded.date()}"
    if dispatch_only:
        return UNUSED, (f"manual-dispatch workflow, last invoked {(now - succeeded).days}d ago — "
                        "idle by design, not stale")

    age = (now - succeeded).days
    if latest is not None:
        latest_at = datetime.fromisoformat(latest["updated_at"].replace("Z", "+00:00"))
        if latest_at >= cutoff:
            # It is running. It is just never winning. This is the signature that hid for five
            # weeks: runs exist, so the pipeline LOOKS alive, and none of them succeed.
            return SILENT, (f"running but not succeeding — last green {age}d ago "
                            f"({succeeded.date()}), most recent run {latest.get('conclusion')!r}")
    return STALE, f"last green {age}d ago ({succeeded.date()}), outside the {window_days}d window"


def sweep(repos: list[str], *, window_days: int = DEFAULT_WINDOW_DAYS,
          now: datetime | None = None) -> list[dict]:
    results = []
    for repo in repos:
        try:
            workflows = list_workflows(repo)
        except SweepError as e:
            # Fail closed: a repo we cannot see is not a repo we can vouch for.
            results.append({"repo": repo, "workflow": "*", "verdict": DEAD,
                            "why": f"could not enumerate workflows: {e}"})
            continue
        for wf in workflows:
            if wf.get("state") != "active":
                continue
            success_at = last_success(repo, wf["id"])
            latest = last_run(repo, wf["id"])
            # only pay for the file read when the answer could change the verdict
            dispatch_only = (is_dispatch_only(repo, wf["path"])
                             if (success_at is None or latest is None) and wf.get("path") else False)
            verdict, why = classify(success_at, latest, window_days=window_days, now=now,
                                    dispatch_only=dispatch_only)
            results.append({"repo": repo, "workflow": wf["name"], "path": wf.get("path"),
                            "verdict": verdict, "why": why})
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ci_liveness_sweep",
        description="Require green RECENTLY. Alarm on staleness, not on failure.")
    ap.add_argument("repos", nargs="*", help="owner/repo (repeatable)")
    ap.add_argument("--repos-file", help="file with one owner/repo per line")
    ap.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-alarm", action="store_true",
                    help="exit non-zero when any workflow is DEAD/SILENT/STALE (use in CI)")
    a = ap.parse_args(argv)

    repos = list(a.repos)
    if a.repos_file:
        repos += [ln.strip() for ln in open(a.repos_file) if ln.strip() and not ln.startswith("#")]
    if not repos:
        ap.error("no repos given")

    results = sweep(repos, window_days=a.window_days)
    alarms = [r for r in results if r["verdict"] in ALARM_VERDICTS]

    if a.json:
        print(json.dumps({"ok": not alarms, "window_days": a.window_days,
                          "checked": len(results), "alarms": alarms, "results": results}, indent=2))
    else:
        for r in sorted(results, key=lambda x: (x["verdict"] == OK, x["repo"])):
            mark = "✓" if r["verdict"] == OK else "✗"
            print(f"  {mark} [{r['verdict']:6}] {r['repo']} :: {r['workflow']} — {r['why']}",
                  file=sys.stderr)
        print(f"\nci liveness: {len(results)} workflow(s) checked, {len(alarms)} alarming "
              f"(window {a.window_days}d)", file=sys.stderr)
        if alarms:
            print("A pipeline that never runs looks exactly like a pipeline with nothing to say.",
                  file=sys.stderr)
    return 1 if (alarms and a.fail_on_alarm) else 0


if __name__ == "__main__":
    raise SystemExit(main())
