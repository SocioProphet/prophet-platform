#!/usr/bin/env python3
"""The verdict rule behind `diagnostics-gate` — the ONE status check the
`main-required-checks` ruleset requires for merging to main.

WHY THIS FILE EXISTS
  The gate used to be a single YAML expression:

      [ "${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') }}" = "false" ]

  It tested `failure` and `cancelled` and nothing else. A GitHub job that is
  *skipped* reports `skipped` — neither of those — so both `contains()` calls
  returned false and the gate went GREEN. When a path filter skipped the
  upstream legs, every needed job reported `skipped` and the sole required
  check for the whole repository passed having verified that nothing ran.

  That is the defect this module closes, and the reason the rule now lives in
  Python: a merge gate that only exists as a YAML expression is a merge gate
  nobody can test. Same argument as tools/ci_docs_only.py, applied to the thing
  that actually decides whether code may land.

TWO PROPERTIES, NOT ONE
  1. Every job wired into the gate's `needs:` genuinely ran and passed, or
     skipped under the one documented filter.               -> verdict()
  2. Every job DECLARED in the workflow file is wired into the gate's `needs:`
     in the first place.                                    -> wiring_verdict()

  (2) is not implied by (1), and that is the whole point of it. `verdict()` can
  only see the jobs GitHub hands it, which is exactly the `needs:` list. A job
  added to validate-target-diagnostics.yml and never added to `needs:` runs, can
  fail, and the one required check for the repository never looks at it. The job
  is correct, the gate is correct, and there is no edge between them — so the
  gate is green while a failing job sits beside it.

FAIL-CLOSED
  ci_docs_only.py fails OPEN (any doubt runs the full matrix) because the worst
  case there is wasted minutes. This module is its mirror image and fails
  CLOSED: an unrecognised result, an unknown job, a missing job, or malformed
  input is a RED gate. The worst case here is unreviewed code reaching main, so
  doubt must block.

CONTRACT
  stdin  : the workflow's `toJSON(needs)` payload
  reads  : .github/workflows/validate-target-diagnostics.yml, for property (2)
  stdout : one line per needed job, then one line per wiring finding, then the
           verdict
  exit   : 0 = gate passes, 1 = gate fails
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Jobs that must have genuinely run and passed. No skip is ever acceptable for
# these, so a path filter added to either one turns the gate RED until someone
# comes here and argues the case in code.
#
#   changes                      — the job that AUTHORISES every skip below. If the
#                                  authoriser did not run, no skip downstream can be
#                                  trusted, whatever it claims.
#   validate-target-diagnostics  — documented COVERAGE-PRESERVING in the workflow: its
#                                  validate-repo leg asserts REQUIRED_FILES exist and
#                                  scans for suspect markers, so documentation is NOT
#                                  inert to it and it runs on every diff.
MUST_SUCCEED = ('changes', 'validate-target-diagnostics')

# Jobs allowed to report `skipped`, and ONLY under the one documented filter:
# `if: always() && needs.changes.outputs.docs_only != 'true'`, whose rule is
# tools/ci_docs_only.py (docs/** and root *.md are inert to application and
# service tests). Skipped for any other reason — an upstream failure, a new
# filter, a mistyped condition — is RED.
DOCS_ONLY_SKIPPABLE = ('app-test-diagnostics', 'smoke-target-diagnostics')

KNOWN_JOBS = MUST_SUCCEED + DOCS_ONLY_SKIPPABLE

# The gate job itself: the ONE job in this workflow legitimately absent from
# `diagnostics-gate`'s `needs:`, because a job cannot depend on itself.
#
# This single literal is the entire self-exclusion, and it is a literal rather
# than a pattern on purpose. The estate has already been burned by the broad
# kind — a ratchet that excluded "its own" entries by pattern ended up counting
# its own allowlist, and only went green AFTER the commit that should have
# failed it. A prefix, suffix or substring rule here would swallow real misses:
# `diagnostics-gate-v2`, `pre-diagnostics-gate` and `diagnostics-gates` are
# different jobs and every one of them must still be caught.
#
# The name is also asserted PRESENT (see wiring_verdict), so the exclusion
# cannot quietly decay into a no-op. That assertion is the first automated
# enforcement of the "DO NOT RENAME THIS JOB" comment in the workflow: this is
# the only context in the `main-required-checks` ruleset and the exact check
# name gitops-promote.yml dispatches this workflow to produce, so a rename
# disables the merge gate estate-wide — silently, until now.
GATE_JOB = 'diagnostics-gate'

WORKFLOW = (Path(__file__).resolve().parents[1]
            / '.github' / 'workflows' / 'validate-target-diagnostics.yml')

AUTHORISING_JOB = 'changes'
AUTHORISING_OUTPUT = 'docs_only'


def verdict(needs: dict) -> tuple[bool, list[str]]:
    """Return (gate_passes, human-readable findings).

    `needs` is the decoded `toJSON(needs)` payload: a mapping of job id to
    {"result": str, "outputs": {...}}.
    """
    findings: list[str] = []
    ok = True

    if not isinstance(needs, dict):
        return False, [f'needs payload is {type(needs).__name__}, not an object']

    # A job wired into `needs:` that this rule has never heard of is unverified
    # coverage: the gate would pass on it by silence. Fail until it is classified.
    # Copilot #1080: surface the reported result + whether outputs are present, so
    # the operator does not have to re-read the JSON payload to decide which
    # bucket the new job belongs in (a success goes to MUST_SUCCEED; a skip
    # that authorises via outputs goes to DOCS_ONLY_SKIPPABLE).
    for job in sorted(set(needs) - set(KNOWN_JOBS)):
        ok = False
        entry = needs.get(job)
        result = entry.get('result') if isinstance(entry, dict) else None
        has_outputs = isinstance(entry, dict) and bool(entry.get('outputs'))
        findings.append(
            f'{job}: wired into the gate but not classified here (reported '
            f'result={result!r}, outputs {"present" if has_outputs else "absent"}) — '
            f'add it to MUST_SUCCEED or DOCS_ONLY_SKIPPABLE in '
            f'tools/ci_diagnostics_gate.py'
        )

    # A job this rule expects but that is absent from the payload means someone
    # removed it from `needs:`, silently dropping it from the merge gate.
    for job in KNOWN_JOBS:
        if job not in needs:
            ok = False
            findings.append(
                f'{job}: expected in the gate\'s `needs:` and absent — the gate '
                f'no longer covers it'
            )

    entry = needs.get(AUTHORISING_JOB)
    outputs = entry.get('outputs') if isinstance(entry, dict) else None
    docs_only = (outputs or {}).get(AUTHORISING_OUTPUT) if isinstance(outputs, dict) else None
    skips_authorised = docs_only == 'true'

    for job in KNOWN_JOBS:
        if job not in needs:
            continue
        entry = needs[job]
        result = entry.get('result') if isinstance(entry, dict) else None

        if result == 'success':
            findings.append(f'{job}: success')
            continue

        if result == 'skipped' and job in DOCS_ONLY_SKIPPABLE and skips_authorised:
            findings.append(
                f'{job}: skipped — authorised by {AUTHORISING_JOB}.outputs.'
                f'{AUTHORISING_OUTPUT}=true (tools/ci_docs_only.py: the diff is '
                f'docs/** and root *.md only, which is inert to app and service tests)'
            )
            continue

        ok = False
        if result == 'skipped' and job in DOCS_ONLY_SKIPPABLE:
            findings.append(
                f'{job}: skipped but NOT authorised — {AUTHORISING_JOB}.outputs.'
                f'{AUTHORISING_OUTPUT}={docs_only!r}, so this diff is not inert and '
                f'these tests were owed'
            )
        elif result == 'skipped':
            findings.append(
                f'{job}: skipped, and it is never allowed to skip — it is the '
                f'coverage this gate exists to guarantee'
            )
        else:
            findings.append(f'{job}: {result!r}')

    return ok, findings


def declared_jobs(text: str) -> list[str]:
    """Top-level job ids in the workflow — parsed positionally, no yaml dep.

    Same idiom, and the same reason, as tools/check_workflow_path_filters.py:
    this rule executes inside the gate job, which has `python3` and no
    `pip install` step, so it reads YAML with the standard library or not at all.

    Scoped to the `jobs:` block deliberately. The trigger keys under `on:`
    (`pull_request`, `push`, `workflow_dispatch`) sit at the same two-space
    indent as job ids, so an unscoped scan reports three phantom "unwired jobs"
    and pins the only required check in the repository red forever.
    """
    block = re.search(r'^jobs:[ \t]*(?:#.*)?$(.*?)(?=^\w|\Z)', text, re.M | re.S)
    if not block:
        return []
    return re.findall(r'^  ([A-Za-z0-9_-]+):[ \t]*(?:#.*)?$', block.group(1), re.M)


def wiring_verdict(text: str | None) -> tuple[bool, list[str]]:
    """Property (2): is every job in the workflow FILE covered by this gate?

    `text` is the workflow source, or None when it could not be read.

    The rule is an equality against KNOWN_JOBS rather than a subset test, and
    that is what makes the two halves of this module compose:

        wiring_verdict : jobs declared in the file, less the gate == KNOWN_JOBS
        verdict        : jobs present in the `needs:` payload     == KNOWN_JOBS
        GitHub         : the `needs:` payload IS the gate's `needs:` list

    Chain them and you get "every job declared in the workflow is in the gate's
    `needs:`" — enforced at runtime, inside the required check itself, without
    this module having to parse the `needs:` list as a third source of truth
    that could drift from the other two.
    """
    if text is None:
        return False, [
            f'{WORKFLOW.name}: could not be read at {WORKFLOW} — the wiring '
            f'property cannot be checked, and an unverifiable gate blocks'
        ]

    declared = set(declared_jobs(text))
    if not declared:
        return False, [
            f'{WORKFLOW.name}: no top-level jobs parsed out of it. Either the '
            f'file moved or its layout changed and this parser has gone blind. '
            f'Blind is RED: it will not vouch for a file it could not read.'
        ]

    findings: list[str] = []
    ok = True

    if GATE_JOB not in declared:
        ok = False
        findings.append(
            f'{GATE_JOB}: not declared in {WORKFLOW.name}. This rule excludes '
            f'exactly that one job id from the wiring check (a job cannot need '
            f'itself), so a rename leaves the exclusion matching nothing while '
            f'the renamed job goes unchecked. It is also the only context in the '
            f'main-required-checks ruleset and the check name gitops-promote.yml '
            f'dispatches for, so renaming it disables the merge gate '
            f'estate-wide. Restore the name.'
        )

    for job in sorted(declared - {GATE_JOB} - set(KNOWN_JOBS)):
        ok = False
        findings.append(
            f'{job}: declared in {WORKFLOW.name} but NOT wired into '
            f'{GATE_JOB}\'s `needs:`. It runs, it can fail, and the one required '
            f'check for this repository never looks at it. Add it to the gate\'s '
            f'`needs:` and classify it in MUST_SUCCEED or DOCS_ONLY_SKIPPABLE.'
        )

    for job in KNOWN_JOBS:
        if job not in declared:
            ok = False
            findings.append(
                f'{job}: classified in tools/ci_diagnostics_gate.py but no longer '
                f'declared in {WORKFLOW.name} — this rule is guarding coverage '
                f'that does not exist. Remove the classification, or restore the '
                f'job.'
            )

    if ok:
        findings.append(
            f'workflow wiring: all {len(declared)} job(s) declared in '
            f'{WORKFLOW.name} are covered by {GATE_JOB} (itself excepted)'
        )
    return ok, findings


def workflow_wiring() -> tuple[bool, list[str]]:
    """`wiring_verdict` against the real file on disk, failing closed if absent."""
    try:
        text = WORKFLOW.read_text(encoding='utf-8', errors='replace')
    except OSError:
        text = None
    return wiring_verdict(text)


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print('FAIL: no needs payload on stdin', file=sys.stderr)
        return 1
    try:
        needs = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f'FAIL: needs payload is not valid JSON: {exc}', file=sys.stderr)
        return 1

    ok, findings = verdict(needs)
    for line in findings:
        print(f'  {line}')

    # Property (2), checked from the file rather than the payload — the payload
    # cannot report a job that was never wired in. Evaluated unconditionally and
    # printed even when the payload verdict has already failed, so one red run
    # shows every reason it is red instead of one reason per push.
    wiring_ok, wiring_findings = workflow_wiring()
    for line in wiring_findings:
        print(f'  {line}')
    ok = ok and wiring_ok

    if ok:
        print('diagnostics-gate: PASS — every job in the workflow is wired into this '
              'gate, and every leg ran or skipped under a documented filter')
        return 0
    # Verdict on stdout, not stderr. Python block-buffers stdout when it is not a
    # TTY, so a verdict written to stderr reaches the Actions log BEFORE the
    # findings that justify it — exactly backwards for whoever is reading a red
    # merge gate. The ::error:: annotation puts the headline in the run summary.
    print('diagnostics-gate: FAIL — an unexplained skip, or a job this gate does not '
          'cover, is a red gate and not a green one')
    print('::error::diagnostics-gate: a needed job did not succeed, skipped without '
          'authorisation, or is declared in the workflow without being wired into this '
          'gate. The per-job verdict is immediately above this line in the log.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
