"""The verdict rule behind `diagnostics-gate`, the ONE required check for merging to main.

The bug this suite exists to prevent recurring: the gate tested `failure` and
`cancelled` but not `skipped`, so a skipped job sailed through and the gate went
green having verified nothing. Most cases below therefore assert the gate is RED —
a merge gate is worth exactly what its negative vectors prove.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ci_diagnostics_gate import (  # noqa: E402
    DOCS_ONLY_SKIPPABLE,
    GATE_JOB,
    KNOWN_JOBS,
    MUST_SUCCEED,
    WORKFLOW,
    declared_jobs,
    verdict,
    wiring_verdict,
    workflow_wiring,
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


def test_unclassified_job_finding_surfaces_reported_result_and_outputs_presence():
    """Copilot #1080: the finding for an unclassified job must include the reported
    `result` and whether `outputs` was present, so the operator picking a bucket
    does not need to re-open the JSON payload. A `success` with `outputs` present
    hints MUST_SUCCEED-with-authorising-output; a bare `skipped` hints the leg is
    absent from an expected fan-out."""
    payload = needs()
    payload['brand-new-diagnostics'] = {'result': 'success', 'outputs': {'x': 'y'}}
    ok, findings = verdict(payload)
    assert ok is False
    hit = next(f for f in findings if f.startswith('brand-new-diagnostics:'))
    assert "reported result='success'" in hit
    assert 'outputs present' in hit
    # And the mirror case: no outputs.
    payload['another-new'] = {'result': 'skipped'}
    ok, findings = verdict(payload)
    assert ok is False
    hit = next(f for f in findings if f.startswith('another-new:'))
    assert "reported result='skipped'" in hit
    assert 'outputs absent' in hit


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


# ══ property 2: every job DECLARED in the workflow is wired into the gate ═════
#
# Everything above validates the jobs the gate was handed — that is, the ones in
# its `needs:`. None of it can see a job added to the workflow file and never
# wired into `needs:` at all. That job runs, it can fail, and the only required
# check for the repository never looks at it: the job is correct, the gate is
# correct, and there is no edge between them.

WORKFLOW_TEXT = WORKFLOW.read_text(encoding='utf-8')

# Every job id the workflow is expected to declare: the four the gate needs,
# plus the gate itself.
ALL_DECLARED = KNOWN_JOBS + (GATE_JOB,)


def workflow_text(*jobs: str) -> str:
    """A synthetic workflow with the same top-level shape as the real one —
    including the `on:` triggers, because their two-space indent is precisely
    what the parser has to not mistake for a job."""
    body = ''.join(
        f'  {job}:\n'
        f'    runs-on: ubuntu-latest\n'
        f'    steps:\n'
        f'      - run: echo {job}\n'
        for job in jobs
    )
    return (
        'name: validate-target-diagnostics\n\n'
        'on:\n'
        '  pull_request:\n'
        '    branches: [ main ]\n'
        '  push:\n'
        '    branches: [ main ]\n'
        '  workflow_dispatch:\n\n'
        'jobs:\n' + body
    )


# ── the ratchet: the real file, not a fixture copy ────────────────────────────

def test_every_job_in_the_real_workflow_is_wired_into_the_gate():
    """THE RATCHET, and the reason this reads the REAL file rather than a
    fixture: add a job to validate-target-diagnostics.yml and this test fails
    until the job is wired into the gate's `needs:` and classified in
    tools/ci_diagnostics_gate.py. A fixture copy would go stale on exactly the
    commit where it mattered."""
    assert set(declared_jobs(WORKFLOW_TEXT)) == set(KNOWN_JOBS) | {GATE_JOB}


def test_the_real_workflow_passes_the_wiring_check_today():
    """The mirror of every red case below. A checker that always fails is as
    broken as one that never does."""
    ok, findings = workflow_wiring()
    assert ok is True, findings


def test_the_module_points_at_the_workflow_it_claims_to():
    """`WORKFLOW` is resolved from __file__; if tools/ ever moves, the gate must
    not end up silently checking a path that does not exist."""
    assert WORKFLOW.exists(), WORKFLOW
    assert WORKFLOW.name == 'validate-target-diagnostics.yml'
    assert WORKFLOW.read_text(encoding='utf-8').startswith('name: validate-target-diagnostics')


# ── the parser, which has no yaml dep and must still be right ─────────────────

def test_the_parser_does_not_mistake_on_triggers_for_jobs():
    """`pull_request`, `push` and `workflow_dispatch` are indented exactly like
    job ids. An unscoped scan reports three phantom unwired jobs and pins the
    repository's only required check red forever."""
    found = declared_jobs(WORKFLOW_TEXT)
    for trigger in ('pull_request', 'push', 'workflow_dispatch'):
        assert trigger not in found


def test_the_parser_ignores_comments_and_nested_keys():
    """Only column-2 keys inside `jobs:` are jobs. Comments at that indent, and
    the deeper keys of a job body, are not."""
    text = (
        'on:\n  push:\n    branches: [ main ]\n\n'
        'jobs:\n'
        '  # commented-out-job:\n'
        '  real-job:  # trailing comment\n'
        '    runs-on: ubuntu-latest\n'
        '    needs: [other]\n'
        '    steps:\n'
        '      - run: |\n'
        '          echo not-a-job:\n'
    )
    assert declared_jobs(text) == ['real-job']


def test_the_regex_parser_agrees_with_a_real_yaml_parser():
    """The gate job runs `python3` with no `pip install`, so the rule parses the
    workflow with a regex. That trade is only safe while the regex agrees with a
    real parser on the real file — so check it here, where pyyaml IS installed
    (the `tools-tests` leg installs it). Imported lazily: an optional dependency
    must never make the merge gate's own test module unimportable."""
    yaml = pytest.importorskip('yaml')
    parsed = yaml.safe_load(WORKFLOW_TEXT)
    assert declared_jobs(WORKFLOW_TEXT) == list(parsed['jobs'])
    # And, while a real parser is to hand, close the loop the runtime rule
    # deduces transitively: the gate's `needs:` list in the file is exactly the
    # classified set.
    assert set(parsed['jobs'][GATE_JOB]['needs']) == set(KNOWN_JOBS)


def test_the_synthetic_fixture_declares_what_the_real_workflow_declares():
    """If the fixture drifted from the real file, every red case below would be
    proving something about a workflow this repo does not have."""
    assert set(declared_jobs(workflow_text(*ALL_DECLARED))) == set(declared_jobs(WORKFLOW_TEXT))


# ── THE GAP ───────────────────────────────────────────────────────────────────

def test_a_fully_wired_workflow_is_green():
    ok, _ = wiring_verdict(workflow_text(*ALL_DECLARED))
    assert ok is True


def test_a_job_added_to_the_file_but_never_wired_into_the_gate_is_red():
    """THE GAP THIS CLOSES. The job runs and can fail; the required check never
    looks at it."""
    ok, findings = wiring_verdict(workflow_text(*ALL_DECLARED, 'orphan-diagnostics'))
    assert ok is False
    assert any(f.startswith('orphan-diagnostics:') for f in findings)


@pytest.mark.parametrize('job', KNOWN_JOBS)
def test_a_classified_job_deleted_from_the_file_is_red(job):
    """The other direction: a classification guarding coverage that no longer
    exists is a stale promise, not a passing gate."""
    remaining = [j for j in ALL_DECLARED if j != job]
    ok, findings = wiring_verdict(workflow_text(*remaining))
    assert ok is False
    assert any(f.startswith(f'{job}:') for f in findings)


# ── the self-exclusion, which is the part most likely to rot ──────────────────

def test_the_gate_job_does_not_trip_its_own_check():
    """`diagnostics-gate` cannot appear in its own `needs:` — a job cannot
    depend on itself — so its absence is legitimate and must not be reported."""
    ok, findings = wiring_verdict(workflow_text(*ALL_DECLARED))
    assert ok is True
    assert not any(f.startswith(f'{GATE_JOB}:') for f in findings)


@pytest.mark.parametrize('lookalike', [
    'diagnostics-gate-v2',
    'diagnostics-gates',
    'pre-diagnostics-gate',
    'diagnostics_gate',
    'Diagnostics-Gate',
    'diagnostics-gate2',
    'gate',
])
def test_the_self_exclusion_is_one_exact_name_and_not_a_pattern(lookalike):
    """The estate has been burned by the broad kind of self-exclusion: a ratchet
    that skipped its own entries by pattern counted its own allowlist and only
    went green AFTER the commit that should have failed it. Every name here is a
    different job from the gate and every one must still be caught."""
    ok, findings = wiring_verdict(workflow_text(*ALL_DECLARED, lookalike))
    assert ok is False
    assert any(f.startswith(f'{lookalike}:') for f in findings)


def test_renaming_the_gate_job_is_red():
    """DO NOT RENAME THIS JOB. `diagnostics-gate` is the only context in the
    main-required-checks ruleset and the exact check name gitops-promote.yml
    dispatches this workflow to produce, so a rename disables the merge gate
    estate-wide. It also leaves the self-exclusion above matching nothing. This
    is the first automated enforcement of that comment."""
    renamed = [j for j in ALL_DECLARED if j != GATE_JOB] + ['merge-gate']
    ok, findings = wiring_verdict(workflow_text(*renamed))
    assert ok is False
    assert any(f.startswith(f'{GATE_JOB}:') and 'not declared' in f for f in findings)


# ── fail-closed when the parser cannot see ────────────────────────────────────

def test_an_unreadable_workflow_is_red():
    """If the file cannot be read the property is unverifiable, and an
    unverifiable merge gate blocks."""
    ok, _ = wiring_verdict(None)
    assert ok is False


@pytest.mark.parametrize('text', [
    '',
    'name: x\non:\n  push:\n    branches: [ main ]\n',   # no jobs: block at all
    'jobs:\n',                                            # jobs: block, no jobs
    'not yaml at all',
    'jobs:\n    over-indented:\n      runs-on: ubuntu-latest\n',
])
def test_a_workflow_with_no_parsable_jobs_is_red(text):
    """A parser that has gone blind must block, never vouch for a file it could
    not read."""
    ok, _ = wiring_verdict(text)
    assert ok is False


# ── end to end, through the entrypoint the gate step actually runs ────────────

def test_cli_goes_red_on_an_unwired_job_and_green_again_when_it_is_removed(tmp_path):
    """Red then green, against the REAL workflow file, through the same
    `python3 tools/ci_diagnostics_gate.py` the gate step invokes.

    The payload is fully green throughout: every needed leg reports success. The
    gate must still fail while an unwired job sits in the file, which is exactly
    the state that used to be invisible. Mutate-and-restore is the idiom
    tools/tests/test_check_workflow_path_filters.py already uses for the same
    reason — a checker only ever run against a passing file is not proven."""
    backup = tmp_path / WORKFLOW.name
    shutil.copy(WORKFLOW, backup)
    original = WORKFLOW.read_text(encoding='utf-8')
    try:
        assert run_cli(json.dumps(needs())).returncode == 0, 'baseline must be green'

        WORKFLOW.write_text(
            original.rstrip('\n')
            + '\n\n  orphan-diagnostics:\n'
              '    runs-on: ubuntu-latest\n'
              '    steps:\n'
              '      - run: exit 1\n',
            encoding='utf-8')
        proc = run_cli(json.dumps(needs()))
        assert proc.returncode != 0, 'a job outside the gate must turn the gate red'
        assert 'orphan-diagnostics' in proc.stdout
    finally:
        shutil.copy(backup, WORKFLOW)

    assert WORKFLOW.read_text(encoding='utf-8') == original
    assert run_cli(json.dumps(needs())).returncode == 0, 'must be green once restored'
