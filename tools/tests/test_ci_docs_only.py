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
    ['docs/design-register.yaml'],
    ['README.md'],
    ['docs/a.md', 'CHANGELOG.md'],
    ['docs/nested/deep/thing.md'],
    ['docs/ARCHITECTURE.md'],          # safe: validate-repo still runs and asserts it exists
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


@pytest.mark.parametrize('path', [
    'docs/conf.py',          # Sphinx config — live Python under docs/
    'docs/scripts/gen.ts',   # a generator that a test could import
    'docs/build.sh',
    'docs/Makefile',
    'docs/notebook.ipynb',
])
def test_executable_files_under_docs_are_not_inert(path):
    """docs/ is not a free pass: it holds live code, and changing that code must
    not skip the tests that cover it (Copilot on #1044)."""
    assert docs_only([path]) is False


@pytest.mark.parametrize('path', [
    'docs/architecture.md',
    'docs/guide/deep/nested.md',
    'README.md',
    'docs/img/diagram.png',   # a doc ASSET, not executable
])
def test_prose_and_assets_under_docs_stay_inert(path):
    assert docs_only([path]) is True
