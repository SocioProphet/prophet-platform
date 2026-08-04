#!/usr/bin/env python3
"""Controls census — the meta-control that reads the SOTA scorecard from reality.

You cannot manage what you cannot see. This program hunts controls that report green while doing
nothing — so the one thing it must not do is let a control's own SOTA properties be asserted by
hand. This enumerates the estate's enforcement controls from the repo and reports, for each,
whether it actually has the properties a real control needs:

  * discriminates — its script carries a negative control / self-test, so it can be shown to FAIL
                    (a gate that cannot fail is the defect this whole program exists to abolish);
  * scheduled     — it runs on its own (a CronJob), not only when a human invokes it;
  * meta-monitored— something alerts if the control itself stops (the check checks the checker).

Two kinds of control are enumerated:
  - scheduled controls: CronJobs under infra/k8s/*/base/cronjob.yaml (+ their ArgoCD app + rule);
  - gate validators: the tools/ scripts wired into `make validate` / `make preflight`.

`--fail-on-undiscriminating` turns the census into a GATE: any control that cannot fail fails the
build. Self-excluding — this reporter is not itself in the census. `--live` enriches with
"ever-fired" from the cluster when reachable; the static census needs no cluster.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).name

# A control "discriminates" if it can be shown to FAIL — either an inline negative control /
# self-test in the script, or a dedicated test file (tools/tests/test_<name>.py) that exercises it.
_DISCRIMINATES_RE = re.compile(
    r"_self_test|--self-test|self.test|_negative_control|negative control|teeth|check_schema|"
    r"must fail|MUST fail|assert .*(==|!=|not )")


def _discriminates(script: Path) -> bool:
    # a co-located test file is the estate's most common negative control
    if (script.parent / "tests" / f"test_{script.stem}.py").is_file():
        return True
    try:
        return bool(_DISCRIMINATES_RE.search(script.read_text(encoding="utf-8", errors="ignore")))
    except OSError:
        return False


def _meta_monitored(base: Path) -> bool:
    return any(base.glob("prometheusrule*.yaml"))


def scheduled_controls(root: Path) -> list[dict]:
    """CronJob-based controls: each infra/k8s/<name>/base/cronjob.yaml."""
    out: list[dict] = []
    for cj in sorted(root.glob("infra/k8s/*/base/cronjob.yaml")):
        base = cj.parent
        name = base.parent.name
        # the mounted script (if any) is the discriminating unit
        scripts = [p for p in base.glob("*.py")]
        discr = any(_discriminates(p) for p in scripts)
        out.append({
            "control": name,
            "kind": "cronjob",
            "discriminates": discr,
            "scheduled": True,
            "meta_monitored": _meta_monitored(base),
            "gitops_app": (root / "deploy/argocd" / f"{name}.yaml").is_file()
                          or any((root / "deploy/argocd").glob(f"*{name}*.yaml")),
        })
    return out


def gate_validators(root: Path) -> list[dict]:
    """tools/ validators wired into `make validate` or `make preflight`."""
    makefile = (root / "Makefile").read_text(encoding="utf-8", errors="ignore") if (root / "Makefile").is_file() else ""
    out: list[dict] = []
    for script in sorted(root.glob("tools/*.py")):
        if script.name == SELF or script.name.startswith("test_"):
            continue
        if not re.match(r"(validate_|verify_|check_|preflight_|selftest_)", script.name):
            continue
        wired = script.name in makefile or script.stem in makefile
        if not wired:
            continue
        out.append({
            "control": script.stem,
            "kind": "validator",
            "discriminates": _discriminates(script),
            "scheduled": False,       # runs in CI on change, not on a wall-clock schedule
            "gate_wired": True,
        })
    return out


def _ever_fired_live(controls: list[dict]) -> None:
    """Best-effort: mark cronjob controls that have a completed Job in the cluster."""
    try:
        raw = subprocess.run(["kubectl", "get", "jobs", "-A", "-o", "json"],
                             capture_output=True, text=True, timeout=30)
        jobs = json.loads(raw.stdout).get("items", []) if raw.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        jobs = []
    names = [j.get("metadata", {}).get("name", "") for j in jobs]
    for c in controls:
        if c["kind"] == "cronjob":
            c["ever_ran"] = any(n.startswith(c["control"]) for n in names)


def census(root: Path, live: bool = False) -> list[dict]:
    controls = scheduled_controls(root) + gate_validators(root)
    if live:
        _ever_fired_live(controls)
    return controls


def _print(controls: list[dict], live: bool) -> None:
    sched = [c for c in controls if c["kind"] == "cronjob"]
    vals = [c for c in controls if c["kind"] == "validator"]
    disc = sum(1 for c in controls if c["discriminates"])
    print(f"Controls census — {len(controls)} controls "
          f"({len(sched)} scheduled, {len(vals)} gate validators)")
    print(f"  discriminate (can actually fail): {disc}/{len(controls)}")
    print("  scheduled controls:")
    for c in sorted(sched, key=lambda x: x["control"]):
        flags = [("discriminates" if c["discriminates"] else "⚠ NO negative control"),
                 ("meta-monitored" if c.get("meta_monitored") else "⚠ no PrometheusRule"),
                 ("gitops" if c.get("gitops_app") else "⚠ no ArgoCD app")]
        if live:
            flags.append("ever-ran" if c.get("ever_ran") else "⚠ never ran")
        print(f"    {c['control']:32s} {' · '.join(flags)}")
    undiscriminating_vals = [c['control'] for c in vals if not c['discriminates']]
    print(f"  gate validators: {len(vals)} ({len(vals) - len(undiscriminating_vals)} discriminate)")
    if undiscriminating_vals:
        print(f"    ⚠ no negative control: {', '.join(undiscriminating_vals)}")


# Shrink-only allowlist: SCHEDULED controls that lack a negative control TODAY (a control that
# cannot be shown to fail). Same ratchet discipline as the moving-tag and ArgoCD-source gates —
# a NEW undiscriminating scheduled control fails the build; a listed one that has SINCE gained a
# negative control fails too (delete it — the ratchet only tightens toward zero). Give each a
# real self-test, then remove it from here.
KNOWN_UNDISCRIMINATING: frozenset[str] = frozenset({
    "pvc-capacity-guard",     # guard.py has no self-test yet
    "rule-liveness-guard",    # guard has no self-test yet (its PrometheusRule is meta-monitoring, not a negative control)
})


def undiscriminating_problems(controls: list[dict]) -> list[str]:
    """Ratchet: new undiscriminating scheduled control OR a stale allowlist entry → a problem."""
    problems: list[str] = []
    scheduled_blind = {c["control"] for c in controls if c["kind"] == "cronjob" and not c["discriminates"]}
    for name in sorted(scheduled_blind - KNOWN_UNDISCRIMINATING):
        problems.append(f"NEW scheduled control with no negative control (cannot be shown to fail): {name} "
                        f"— add a self-test, or it is a paper control")
    scheduled_all = {c["control"] for c in controls if c["kind"] == "cronjob"}
    for name in sorted(KNOWN_UNDISCRIMINATING & scheduled_all - scheduled_blind):
        problems.append(f"STALE allowlist entry: {name} now HAS a negative control — remove it from "
                        f"KNOWN_UNDISCRIMINATING (the ratchet only shrinks)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Census of the estate's enforcement controls.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--live", action="store_true", help="enrich with ever-ran from the cluster")
    ap.add_argument("--fail-on-undiscriminating", action="store_true",
                    help="exit non-zero if any SCHEDULED control lacks a negative control")
    args = ap.parse_args(argv)
    controls = census(ROOT, live=args.live)
    if args.json:
        print(json.dumps(controls, indent=2))
    else:
        _print(controls, args.live)
    if args.fail_on_undiscriminating:
        problems = undiscriminating_problems(controls)
        if problems:
            print(f"FAIL: {len(problems)} controls-census ratchet problem(s):")
            for p in problems:
                print(f"  {p}")
            return 1
        n_allow = len(KNOWN_UNDISCRIMINATING)
        print(f"OK: no NEW undiscriminating scheduled control ({n_allow} known, shrink-only: "
              f"{', '.join(sorted(KNOWN_UNDISCRIMINATING))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
