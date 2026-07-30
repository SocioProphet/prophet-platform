"""The skip rule that decides whether app-test/smoke legs may be skipped.

A CI optimisation that silently stops running tests is worse than no optimisation, so this
suite is adversarial: most cases assert that we DO run everything.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ci_docs_only import docs_only  # noqa: E402


@pytest.mark.parametrize('paths', [
    ['README.md'],
    ['docs/a.md', 'CHANGELOG.md'],
    ['docs/nested/deep/thing.md'],
    ['docs/ARCHITECTURE.md'],          # safe: validate-repo still runs and asserts it exists
    ['docs/img/diagram.png'],
    ['docs/notes.rst', 'docs/notes.txt'],
    ['docs/A.MD'],                     # extension match is case-insensitive
])
def test_inert_diffs_may_skip_the_app_and_smoke_legs(paths):
    assert docs_only(paths) is True


@pytest.mark.parametrize('paths', [
    ['apps/compute-gateway/src/x.py'],
    ['tools/premerge_audit.py'],
    ['.github/workflows/ci.yml'],
    ['infra/k8s/overlays/x.yaml'],
    ['contracts/platform/thing.yaml'],
    ['Makefile'],
    ['go.work'],
])
def test_code_and_infra_always_run_everything(paths):
    assert docs_only(paths) is False


def test_one_code_file_among_many_docs_forces_a_full_run():
    """The failure mode that matters: a big docs PR hiding a single code edit."""
    paths = [f'docs/note{i}.md' for i in range(50)] + ['apps/api/main.go']
    assert docs_only(paths) is False


def test_an_empty_diff_proves_nothing_and_runs_everything():
    assert docs_only([]) is False
    assert docs_only(['', '  ']) is False


@pytest.mark.parametrize('path', [
    'docsomething/x.py',      # prefix collision — must not be read as docs/
    'apps/svc/README.md',     # markdown, but NOT top-level, and it sits beside code
    'infra/docs/x.py',        # 'docs' appears, but not at the root
])
def test_near_misses_do_not_earn_a_skip(path):
    assert docs_only([path]) is False


def test_the_rule_is_all_or_nothing():
    """Skipping requires EVERY path to be inert — proof of inertness, not a majority vote."""
    assert docs_only(['docs/a.md', 'docs/b.md']) is True
    assert docs_only(['docs/a.md', 'apps/x.py']) is False


# ---------------------------------------------------------------------------
# Copilot #1044 (ci_docs_only.py:36 and :29): "anything under docs/ is inert" is a
# coverage hole that opens itself. docs/ can hold executable and machine-consumed
# files, and the moment one appears it is silently exempted from app-test and smoke.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('path', [
    'docs/conf.py',                       # Sphinx config — executable
    'docs/scripts/gen.ts',
    'docs/scripts/build.sh',
    'docs/tooling/helper.js',
    'docs/design-register.yaml',          # this repo HAS this, and a workflow reads it
    'docs/generated/identity/examples/identity_session_context.example.v0.1.json',
    'docs/Makefile',                      # no extension at all
    'docs/.env',
])
def test_an_executable_or_machine_consumed_file_under_docs_is_not_inert(path):
    assert docs_only([path]) is False, f'{path} must not earn a skip'


def test_a_code_file_hidden_in_a_docs_only_diff_forces_a_full_run():
    """The exploit shape: a large, plausibly docs-only PR carrying one executable path."""
    paths = [f'docs/note{i}.md' for i in range(30)] + ['docs/scripts/postinstall.py']
    assert docs_only(paths) is False


def test_the_detector_is_not_inert_to_itself():
    """A PR editing the skip rule must run the full matrix. Together with reading the
    detector from the base ref, this is what stops it certifying its own modification."""
    assert docs_only(['tools/ci_docs_only.py']) is False
    assert docs_only(['tools/tests/test_ci_docs_only.py']) is False
    assert docs_only(['.github/workflows/validate-target-diagnostics.yml']) is False


# ---------------------------------------------------------------------------
# The trust boundary itself. Structural, because the property lives in YAML: the
# workflow must execute the BASE ref's detector, not the PR checkout's copy.
# ---------------------------------------------------------------------------

WORKFLOW = REPO_ROOT / '.github' / 'workflows' / 'validate-target-diagnostics.yml'


def _changes_job_script() -> str:
    """The `changes` job's detect step, as text. Deliberately not a YAML-schema
    assertion — what matters is the shell that actually runs."""
    import yaml

    wf = yaml.safe_load(WORKFLOW.read_text())
    steps = wf['jobs']['changes']['steps']
    detect = [s for s in steps if s.get('id') == 'detect']
    assert len(detect) == 1, 'expected exactly one detect step in the changes job'
    return detect[0]['run']


def test_the_detector_is_read_from_the_base_ref_not_the_pr_checkout():
    """Copilot #1044 (:66), unanswered: running `python3 tools/ci_docs_only.py` executes
    the PR's own copy. A PR could edit it to print "true" unconditionally and skip
    app-test and smoke for its whole diff — self-certification."""
    script = _changes_job_script()
    assert 'git show "origin/$BASE:tools/ci_docs_only.py"' in script, \
        'the detector must be read from the base ref'
    assert 'python3 tools/ci_docs_only.py' not in script, \
        'executing the PR checkout of the detector lets a PR certify its own skip'


def test_an_unreadable_base_detector_runs_everything():
    """Fail-safe, not fail-open: if the base copy cannot be read, the full matrix runs."""
    script = _changes_job_script()
    marker = 'git show "origin/$BASE:tools/ci_docs_only.py"'
    tail = script.split(marker, 1)[1]
    guard = tail.split('fi', 1)[0]
    assert 'docs_only=false' in guard, \
        'a detector that cannot be read from the base ref must fall back to running everything'
