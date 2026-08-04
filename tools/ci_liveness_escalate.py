#!/usr/bin/env python3
"""Escalation — the half that makes a finding land on someone.

`ci_liveness_sweep.py` measures. This raises.

In John 11 both sisters send word, and they do different things. **Martha** goes out to meet him,
reports, and makes the measurement — *"he stinketh, for he hath been dead four days"*: observed,
dated, quantified. And after her report he **stayed two more days**. **Mary** waits until she is
called, and when she comes she falls at his feet and weeps — and that is the hinge. *"When Jesus
saw her weeping... he groaned in the spirit."* Then, and not before: *"Where have ye laid him?"*

    MARTHA IS DETECTION. MARY IS ESCALATION.
    Information did not raise anyone. Grief that landed on someone did.

A sweep that prints to stderr and exits non-zero is all Martha. If nobody runs it, or runs it and
reads past it, nothing happens — which is precisely how this estate accumulated a stranded-work
register: findings were made, and then they sat.

So this writes a durable, addressed, self-updating artifact — a GitHub issue per repo — and:

  * **is idempotent.** It updates one issue per repo rather than filing a new one each sweep.
    Alarm spam is how a channel gets muted, and a muted channel is a dead control.

  * **ESCALATES WITH AGE.** This is the load-bearing property. A finding that has been seen and not
    acted on gets *louder*, never quieter. The natural failure of any monitoring system is that an
    old alarm becomes furniture — so silence that persists must become harder to ignore, not
    easier. Grief that does not resolve escalates.

  * **CLOSES ITSELF when the pipeline is green again.** The mourning ends at the raising. An issue
    that stays open after the fact is noise, and noise is what taught everyone to stop reading.

stdlib + `gh`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

MARKER = "<!-- ci-liveness-sweep: do not remove; this issue is updated in place -->"

# Escalation ladder. The point is that sitting still moves you DOWN this table.
TIERS = [
    (90, "P0", "ci-liveness:P0", "ninety days silent — treat as an outage that nobody declared"),
    (60, "P1", "ci-liveness:P1", "two months silent"),
    (30, "P2", "ci-liveness:P2", "one month silent"),
    (0,  "P3", "ci-liveness:P3", "recently silent"),
]


def tier_for(max_age_days: int) -> tuple[str, str, str]:
    for threshold, sev, label, phrase in TIERS:
        if max_age_days >= threshold:
            return sev, label, phrase
    return "P3", "ci-liveness:P3", "recently silent"


def _gh(args: list[str], check: bool = True) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}… failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def find_issue(repo: str) -> dict | None:
    """The one issue this tool owns for a repo, found by its marker rather than by title —
    titles change as severity escalates."""
    out = _gh(["issue", "list", "--repo", repo, "--state", "open", "--limit", "100",
               "--json", "number,title,body"], check=False)
    try:
        for issue in json.loads(out or "[]"):
            if MARKER in (issue.get("body") or ""):
                return issue
    except json.JSONDecodeError:
        return None
    return None


def age_days(why: str) -> int:
    """Pull the age out of the sweep's own reason string. Absent an age, treat as maximally old:
    a verdict we cannot date is not a verdict we may discount."""
    import re
    m = re.search(r"(\d+)d ago", why)
    if m:
        return int(m.group(1))
    return 9999 if "never" in why else 0


def render(repo: str, alarms: list[dict], window_days: int) -> tuple[str, str, str]:
    worst = max((age_days(a["why"]) for a in alarms), default=0)
    sev, label, phrase = tier_for(worst)
    shown = "never green" if worst >= 9999 else f"{worst}d"
    title = f"[{sev}] CI liveness: {len(alarms)} workflow(s) not green in {repo} (worst: {shown})"

    lines = [MARKER, "",
             f"**{len(alarms)} workflow(s) have not completed successfully inside the "
             f"{window_days}-day window** — {phrase}.", "",
             "A red build is information. A build that never runs produces the same observable as "
             "a passing build: no reported failures. This issue exists so that absence has an "
             "address.", "",
             "| workflow | verdict | detail |", "|---|---|---|"]
    for a in sorted(alarms, key=lambda x: -age_days(x["why"])):
        lines.append(f"| `{a['workflow']}` | **{a['verdict']}** | {a['why']} |")
    lines += ["",
              "### This issue escalates",
              "",
              "It is updated in place by `tools/ci_liveness_sweep.py` + `ci_liveness_escalate.py`, "
              "and its severity **rises with the age of the silence**. A finding that is seen and "
              "not acted on gets louder, never quieter — the natural failure of monitoring is that "
              "an old alarm becomes furniture.",
              "",
              "**It closes itself** once every workflow here is green again. The mourning ends at "
              "the raising.",
              "", "See `docs/CI_LIVENESS.md`."]
    return title, "\n".join(lines), label


def escalate(repo: str, alarms: list[dict], window_days: int, *, dry_run: bool = False) -> str:
    existing = find_issue(repo)

    if not alarms:
        if existing and not dry_run:
            _gh(["issue", "comment", str(existing["number"]), "--repo", repo,
                 "--body", "All swept workflows are green again — closing. The mourning ends at "
                           "the raising."], check=False)
            _gh(["issue", "close", str(existing["number"]), "--repo", repo], check=False)
            return f"{repo}: RESOLVED — closed #{existing['number']}"
        return f"{repo}: green, nothing to raise"

    title, body, label = render(repo, alarms, window_days)
    if dry_run:
        return f"{repo}: would {'update #' + str(existing['number']) if existing else 'open'} — {title}"

    if existing:
        _gh(["issue", "edit", str(existing["number"]), "--repo", repo,
             "--title", title, "--body", body], check=False)
        _gh(["issue", "edit", str(existing["number"]), "--repo", repo,
             "--add-label", label], check=False)
        return f"{repo}: updated #{existing['number']} — {title}"

    out = _gh(["issue", "create", "--repo", repo, "--title", title, "--body", body], check=False)
    return f"{repo}: opened — {out.strip().splitlines()[-1] if out.strip() else title}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ci_liveness_escalate",
        description="Turn a sweep result into an addressed, self-updating, escalating issue.")
    ap.add_argument("--sweep-json", required=True,
                    help="output of `ci_liveness_sweep.py --json` ('-' for stdin)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    raw = sys.stdin.read() if a.sweep_json == "-" else open(a.sweep_json).read()
    data = json.loads(raw)
    window = data.get("window_days", 14)

    by_repo: dict[str, list[dict]] = {}
    for r in data.get("results", []):
        by_repo.setdefault(r["repo"], [])
    for r in data.get("alarms", []):
        by_repo.setdefault(r["repo"], []).append(r)

    for repo, alarms in sorted(by_repo.items()):
        print("  " + escalate(repo, alarms, window, dry_run=a.dry_run), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
