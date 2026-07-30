"""The verdict rule behind `diagnostics-gate`, the ONE required check for merging to main.

The bug this suite exists to prevent recurring: the gate tested `failure` and
`cancelled` but not `skipped`, so a skipped job sailed through and the gate went
green having verified nothing. Most cases below therefore assert the gate is RED —
a merge gate is worth exactly what its negative vectors prove.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ci_diagnostics_gate import (  # noqa: E402
    DOCS_ONLY_SKIPPABLE,
    KNOWN_JOBS,
    MUST_SUCCEED,
    verdict,
)

ALL_RESULTS = ('success', 'failure', 'cancelled', 'skipped')


def needs(*, changes='success', validate='success', app='success', smoke='success',
          docs_only='false'):
    """A `toJSON(needs)` payload shaped exactly as GitHub emits it."""
    return {
        'changes': {'result': changes, 'outputs': {'docs_only': docs_only}},
        'validate-target-diagnostics': {'result': validate, 'outputs': {}},
        'app-test-diagnostics': {'result': app, 'outputs': {}},
        'smoke-target-diagnostics': {'result': smoke, 'outputs': {}},
    }


# ── the happy paths ───────────────────────────────────────────────────────────

def test_every_leg_green_passes():
    ok, _ = verdict(needs())
    assert ok is True


def test_docs_only_skip_of_app_and_smoke_is_authorised():
    """The one documented filter: docs/** and root *.md are inert to app/service tests."""
    ok, findings = verdict(needs(app='skipped', smoke='skipped', docs_only='true'))
    assert ok is True
    assert any('authorised' in f for f in findings)


def test_docs_only_true_does_not_require_the_skip():
    """A docs-only diff that runs the legs anyway is still perfectly green."""
    ok, _ = verdict(needs(docs_only='true'))
    assert ok is True


# ── the regression this module was written for ────────────────────────────────

@pytest.mark.parametrize('job', KNOWN_JOBS)
def test_a_skipped_job_without_authorisation_is_red(job):
    """THE BUG. `skipped` is neither 'failure' nor 'cancelled'; the old gate passed it."""
    payload = needs()
    payload[job]['result'] = 'skipped'
    ok, _ = verdict(payload)
    assert ok is False, f'{job} skipped with docs_only=false must fail the gate'


def test_everything_skipped_is_red():
    """The live scenario: a path filter skips every leg and the gate verifies nothing."""
    ok, _ = verdict(needs(changes='skipped', validate='skipped', app='skipped',
                          smoke='skipped'))
    assert ok is False


def test_everything_skipped_is_red_even_when_docs_only_claims_true():
    """docs_only only ever authorises the app and smoke legs — never the validators."""
    ok, _ = verdict(needs(changes='skipped', validate='skipped', app='skipped',
                          smoke='skipped', docs_only='true'))
    assert ok is False


@pytest.mark.parametrize('job', MUST_SUCCEED)
def test_the_always_on_jobs_may_never_skip(job):
    payload = needs(docs_only='true')
    payload[job]['result'] = 'skipped'
    ok, _ = verdict(payload)
    assert ok is False, f'{job} must run on every diff, docs-only included'


def test_a_skipped_authoriser_cannot_authorise_its_own_skip():
    """If `changes` did not run, its outputs are empty and prove nothing."""
    payload = needs(changes='skipped', app='skipped', smoke='skipped')
    payload['changes']['outputs'] = {}
    ok, _ = verdict(payload)
    assert ok is False


# ── the behaviour the old gate did get right, which must not regress ──────────

@pytest.mark.parametrize('job', KNOWN_JOBS)
@pytest.mark.parametrize('bad', ['failure', 'cancelled'])
def test_failure_and_cancellation_stay_red(job, bad):
    payload = needs()
    payload[job]['result'] = bad
    ok, _ = verdict(payload)
    assert ok is False


@pytest.mark.parametrize('bad', ['failure', 'cancelled'])
def test_a_failing_leg_is_red_even_on_a_docs_only_diff(bad):
    payload = needs(docs_only='true')
    payload['app-test-diagnostics']['result'] = bad
    ok, _ = verdict(payload)
    assert ok is False


# ── fail-closed on anything unrecognised ──────────────────────────────────────

@pytest.mark.parametrize('result', ['', None, 'neutral', 'timed_out', 'SUCCESS', 'sucess'])
def test_an_unrecognised_result_is_red(result):
    """Only the literal string 'success' is success. Case included."""
    payload = needs()
    payload['app-test-diagnostics']['result'] = result
    ok, _ = verdict(payload)
    assert ok is False


def test_a_job_removed_from_needs_is_red():
    """Dropping a job from `needs:` silently removes it from the merge gate."""
    payload = needs()
    del payload['smoke-target-diagnostics']
    ok, _ = verdict(payload)
    assert ok is False


def test_an_unclassified_job_added_to_needs_is_red():
    """A new leg must be classified here, or the gate would pass on it by silence."""
    payload = needs()
    payload['brand-new-diagnostics'] = {'result': 'success', 'outputs': {}}
    ok, _ = verdict(payload)
    assert ok is False


def test_an_empty_payload_is_red():
    ok, _ = verdict({})
    assert ok is False


@pytest.mark.parametrize('payload', [[], 'success', None, 42])
def test_a_malformed_payload_is_red(payload):
    ok, _ = verdict(payload)
    assert ok is False


@pytest.mark.parametrize('docs_only', ['True', 'TRUE', '1', 'yes', '', None, True])
def test_only_the_literal_string_true_authorises_a_skip(docs_only):
    """GitHub outputs are strings; anything but 'true' leaves the skip unauthorised."""
    payload = needs(app='skipped', smoke='skipped', docs_only=docs_only)
    ok, _ = verdict(payload)
    assert ok is False


def test_missing_outputs_block_do_not_authorise_a_skip():
    payload = needs(app='skipped', smoke='skipped')
    del payload['changes']['outputs']
    ok, _ = verdict(payload)
    assert ok is False


# ── exhaustive truth table, so no combination is left to inference ────────────

@pytest.mark.parametrize('app', ALL_RESULTS)
@pytest.mark.parametrize('smoke', ALL_RESULTS)
@pytest.mark.parametrize('docs_only', ['true', 'false'])
def test_truth_table_for_the_skippable_legs(app, smoke, docs_only):
    def leg_ok(result):
        return result == 'success' or (result == 'skipped' and docs_only == 'true')

    expected = leg_ok(app) and leg_ok(smoke)
    ok, _ = verdict(needs(app=app, smoke=smoke, docs_only=docs_only))
    assert ok is expected


@pytest.mark.parametrize('result', ALL_RESULTS)
@pytest.mark.parametrize('job', MUST_SUCCEED)
@pytest.mark.parametrize('docs_only', ['true', 'false'])
def test_truth_table_for_the_always_on_jobs(job, result, docs_only):
    payload = needs(docs_only=docs_only)
    payload[job]['result'] = result
    ok, _ = verdict(payload)
    assert ok is (result == 'success')


# ── the module is invoked as a process by the workflow, so test it that way ───

def run_cli(stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / 'tools' / 'ci_diagnostics_gate.py')],
        input=stdin, capture_output=True, text=True, check=False,
    )


def test_cli_exits_zero_when_green():
    assert run_cli(json.dumps(needs())).returncode == 0


def test_cli_exits_nonzero_on_an_unauthorised_skip():
    proc = run_cli(json.dumps(needs(app='skipped', smoke='skipped')))
    assert proc.returncode != 0


@pytest.mark.parametrize('stdin', ['', '   ', 'not json', '{"changes":'])
def test_cli_fails_closed_on_unusable_input(stdin):
    """A gate that cannot read its inputs must block, never wave the merge through."""
    assert run_cli(stdin).returncode != 0


def test_the_classification_lists_are_disjoint_and_complete():
    assert set(MUST_SUCCEED) & set(DOCS_ONLY_SKIPPABLE) == set()
    assert set(KNOWN_JOBS) == set(MUST_SUCCEED) | set(DOCS_ONLY_SKIPPABLE)
