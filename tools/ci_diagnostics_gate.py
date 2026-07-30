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

FAIL-CLOSED
  ci_docs_only.py fails OPEN (any doubt runs the full matrix) because the worst
  case there is wasted minutes. This module is its mirror image and fails
  CLOSED: an unrecognised result, an unknown job, a missing job, or malformed
  input is a RED gate. The worst case here is unreviewed code reaching main, so
  doubt must block.

CONTRACT
  stdin  : the workflow's `toJSON(needs)` payload
  stdout : one line per needed job, then the verdict
  exit   : 0 = gate passes, 1 = gate fails
"""
from __future__ import annotations

import json
import sys

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
    if ok:
        print('diagnostics-gate: PASS — every leg ran, or skipped under a documented filter')
        return 0
    # Verdict on stdout, not stderr. Python block-buffers stdout when it is not a
    # TTY, so a verdict written to stderr reaches the Actions log BEFORE the
    # findings that justify it — exactly backwards for whoever is reading a red
    # merge gate. The ::error:: annotation puts the headline in the run summary.
    print('diagnostics-gate: FAIL — an unexplained skip is a red gate, not a green one')
    print('::error::diagnostics-gate: a needed job did not succeed, or skipped without '
          'authorisation. The per-job verdict is immediately above this line in the log.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
