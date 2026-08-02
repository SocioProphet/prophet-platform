#!/usr/bin/env python3
"""Prove that every GitHub Actions job declares a runaway bound (`timeout-minutes`).

An Actions job with no `timeout-minutes` inherits GitHub's default of **360
minutes (6 hours)**.  A single hung step therefore burns six hours of the
shared, spend-capped Actions allowance before the platform kills it — and while
it burns, the runner it holds is unavailable to every other PR, so the queue
reads as "saturation" and merges stall behind a bill, not a bug.  That is the
class-C failure ("budget masqueraded as failure") in
`docs/architecture/devsecops-retrospective-and-recovery-v0.1.md`: the 6h hang
did not just cost money, it *caused* the queue that looked like an outage.

A bound is cheap insurance.  This checker fails if any job can run unbounded.

Design notes (each earned from a real defect in this estate):

* We parse real YAML (PyYAML, already a `tools/` dependency), not line-1 regex.
  A checker that reads only the first physical line of a block vouches for what
  it never saw — that exact bug shipped in the path-filter auditor (PR #1101).
* A file that will not parse is an ERROR, never a silent skip.  "Unparseable ->
  ignored" is how a scan reports green over ground it never read.
* An **empty** scan is an ERROR, not a pass.  A checker that reports success
  because it found nothing to check is the "control that cannot fail" disease
  (class A).  Point us at a dir with no workflows and we exit non-zero.
* Jobs that *call a reusable workflow* (`uses:` at job level) may not legally
  carry `timeout-minutes` (GitHub rejects it).  We do not fail them — but we
  list them explicitly so the bound owed by the called workflow stays visible,
  rather than being silently assumed.

Exit status: 0 iff every non-exempt job declares a positive `timeout-minutes`
and at least one workflow was scanned; 1 otherwise.

Prove-it-fires: `tools/selftest_check_workflow_timeout_bounds.py` drives a
known-unbounded fixture (must go RED) and a known-bounded fixture (must go
GREEN).  Never trust this green until you have watched it go red.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOWS = ROOT / ".github" / "workflows"

# GitHub's implicit job timeout when `timeout-minutes` is absent.
GITHUB_DEFAULT_TIMEOUT_MINUTES = 360


class Finding:
    __slots__ = ("workflow", "job", "kind", "detail")

    def __init__(self, workflow: str, job: str, kind: str, detail: str) -> None:
        self.workflow = workflow
        self.job = job
        self.kind = kind  # "unbounded" | "bad-value" | "parse-error" | "empty-scan"
        self.detail = detail

    def as_dict(self) -> dict[str, str]:
        return {"workflow": self.workflow, "job": self.job, "kind": self.kind, "detail": self.detail}


def _is_reusable_call(job: dict[str, Any]) -> bool:
    """A job that is `uses: org/repo/.github/workflows/x.yml@ref` calls a reusable
    workflow.  GitHub forbids `timeout-minutes` on such a job; the bound must live
    in the called workflow.  We exempt but surface these, never assume them."""
    return isinstance(job.get("uses"), str)


def _valid_timeout(value: Any) -> bool:
    # Accept positive ints; reject 0, negatives, strings, floats-as-str, None.
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def audit_file(path: Path) -> tuple[list[Finding], list[str], int]:
    """Return (findings, exempt_reusable_jobs, bounded_job_count) for one workflow."""
    rel = path.name
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # unreadable file is a hard error, not a pass
        return [Finding(rel, "-", "parse-error", f"unreadable: {exc}")], [], 0
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [Finding(rel, "-", "parse-error", f"yaml: {exc}")], [], 0

    if not isinstance(doc, dict):
        return [Finding(rel, "-", "parse-error", "top-level is not a mapping")], [], 0

    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        # A workflow file with no jobs mapping is malformed for our purposes.
        return [Finding(rel, "-", "parse-error", "no `jobs:` mapping")], [], 0

    findings: list[Finding] = []
    exempt: list[str] = []
    bounded = 0
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            findings.append(Finding(rel, str(job_name), "parse-error", "job is not a mapping"))
            continue
        if _is_reusable_call(job):
            exempt.append(f"{rel}:{job_name}")
            continue
        if "timeout-minutes" not in job:
            findings.append(
                Finding(rel, str(job_name), "unbounded",
                        f"no timeout-minutes -> inherits GitHub default {GITHUB_DEFAULT_TIMEOUT_MINUTES}m (6h)")
            )
            continue
        value = job["timeout-minutes"]
        if not _valid_timeout(value):
            findings.append(
                Finding(rel, str(job_name), "bad-value",
                        f"timeout-minutes={value!r} is not a positive integer")
            )
            continue
        bounded += 1
    return findings, exempt, bounded


def discover_workflows(workflows_dir: Path) -> list[Path]:
    if not workflows_dir.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(workflows_dir.iterdir()):
        if p.is_file() and p.suffix in (".yml", ".yaml"):
            out.append(p)
    return out


def run(workflows_dir: Path, as_json: bool) -> int:
    files = discover_workflows(workflows_dir)
    all_findings: list[Finding] = []
    all_exempt: list[str] = []
    total_bounded = 0

    if not files:
        # Empty scan is a failure, not a pass (a green from nothing is a lie).
        finding = Finding(str(workflows_dir), "-", "empty-scan",
                          "no *.yml/*.yaml workflow files found -- refusing to report green")
        if as_json:
            print(json.dumps({"ok": False, "scanned_workflows": 0, "findings": [finding.as_dict()]}, indent=2))
        else:
            print(f"ERROR: {finding.detail} (looked in {workflows_dir})")
        return 1

    for f in files:
        findings, exempt, bounded = audit_file(f)
        all_findings.extend(findings)
        all_exempt.extend(exempt)
        total_bounded += bounded

    total_jobs = total_bounded + len(all_exempt) + sum(
        1 for x in all_findings if x.kind in ("unbounded", "bad-value")
    )
    unbounded = [x for x in all_findings if x.kind == "unbounded"]
    bad_value = [x for x in all_findings if x.kind == "bad-value"]
    parse_errors = [x for x in all_findings if x.kind == "parse-error"]
    ok = not all_findings

    if as_json:
        print(json.dumps({
            "ok": ok,
            "scanned_workflows": len(files),
            "total_jobs": total_jobs,
            "bounded_jobs": total_bounded,
            "unbounded_jobs": len(unbounded),
            "bad_value_jobs": len(bad_value),
            "reusable_exempt_jobs": len(all_exempt),
            "parse_errors": len(parse_errors),
            "findings": [x.as_dict() for x in all_findings],
            "reusable_exempt": all_exempt,
        }, indent=2))
        return 0 if ok else 1

    print(f"Scanned {len(files)} workflow file(s) in {workflows_dir}")
    print(f"  jobs total (non-exempt + exempt): {total_jobs}")
    print(f"  bounded (declare timeout-minutes): {total_bounded}")
    print(f"  reusable-workflow calls (exempt, bound owed by callee): {len(all_exempt)}")
    print(f"  UNBOUNDED jobs (inherit {GITHUB_DEFAULT_TIMEOUT_MINUTES}m default): {len(unbounded)}")
    if bad_value:
        print(f"  BAD timeout-minutes values: {len(bad_value)}")
    if parse_errors:
        print(f"  PARSE ERRORS (fail-closed): {len(parse_errors)}")
    if unbounded:
        print("\nUnbounded jobs (each a 6h budget bomb):")
        for x in unbounded:
            print(f"  - {x.workflow}:{x.job}")
    if bad_value:
        print("\nInvalid timeout-minutes:")
        for x in bad_value:
            print(f"  - {x.workflow}:{x.job}  ({x.detail})")
    if parse_errors:
        print("\nParse errors (treated as failures, never skipped):")
        for x in parse_errors:
            print(f"  - {x.workflow}:{x.job}  ({x.detail})")
    if all_exempt:
        print("\nReusable-workflow calls (exempt; verify the callee is bounded):")
        for e in all_exempt:
            print(f"  - {e}")
    print("\nRESULT:", "PASS -- every job is bounded" if ok else "FAIL -- unbounded/invalid jobs above")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit GitHub Actions jobs for a runaway `timeout-minutes` bound.")
    ap.add_argument("--workflows-dir", type=Path, default=DEFAULT_WORKFLOWS,
                    help="directory of workflow YAML files (default: .github/workflows)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    return run(args.workflows_dir, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
