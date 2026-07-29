"""premerge_audit against REAL git repositories.

A merge gate mocked at the subprocess boundary proves only that the mocks agree with each
other. Every case here builds an actual repo with an actual divergence, so the assertions
are about git's real answers.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import premerge_audit  # noqa: E402


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


def write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo with `main` and a `feature` branch that diverged after a common base."""
    r = tmp_path / 'r'
    r.mkdir()
    git(r, 'init', '-q', '-b', 'main')
    git(r, 'config', 'user.email', 't@t')
    git(r, 'config', 'user.name', 't')
    write(r, 'README.md', 'base\n')
    write(r, 'apps/svc/main.py', 'base\n')
    write(r, 'docs/notes.md', 'base\n')
    git(r, 'add', '-A')
    git(r, 'commit', '-qm', 'base')
    git(r, 'branch', 'feature')
    # point the module at this repo
    monkeypatch.setattr(premerge_audit, 'ROOT', r)
    return r


def advance_main(repo: Path, rel: str, text: str, msg: str = 'main moves') -> None:
    git(repo, 'checkout', '-q', 'main')
    write(repo, rel, text)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', msg)


def commit_on_feature(repo: Path, rel: str, text: str, msg: str = 'feature work') -> None:
    git(repo, 'checkout', '-q', 'feature')
    write(repo, rel, text)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', msg)


def audit(repo: Path, **kw):
    git(repo, 'checkout', '-q', 'feature')
    return premerge_audit.audit('main', 'HEAD', **kw)


def test_current_branch_passes(repo: Path):
    commit_on_feature(repo, 'docs/notes.md', 'changed\n')
    code, out = audit(repo)
    assert code == 0
    assert any('branch is current' in line for line in out)


def test_the_starvation_case_now_passes_when_nothing_overlaps(repo: Path):
    """THE regression this change exists to prevent: a docs-only PR blocked because an
    unrelated service moved on main. Behind > 0, zero overlap => safe."""
    commit_on_feature(repo, 'docs/notes.md', 'my docs\n')
    advance_main(repo, 'apps/other/thing.py', 'unrelated\n')
    advance_main(repo, 'apps/other/more.py', 'also unrelated\n', 'main moves again')
    code, out = audit(repo)
    assert code == 0, out
    assert any('staleness cannot affect this change' in line for line in out)
    assert any(line == 'behind=2' for line in out), 'still reports the drift honestly'


def test_overlap_is_refused_even_though_git_could_automerge(repo: Path):
    """The case the OLD gate missed in the other direction: both sides edited the same file.
    Different lines, git merges fine — and it is still a real conflict surface."""
    commit_on_feature(repo, 'docs/notes.md', 'base\nmine at the bottom\n')
    advance_main(repo, 'docs/notes.md', 'theirs at the top\nbase\n')
    code, out = audit(repo)
    assert code == 1
    assert any('REFUSED' in line and 'conflict surface' in line for line in out)
    assert any(' - docs/notes.md' in line for line in out), 'names the offending file'


def test_hot_path_overlap_is_refused_with_its_own_reason(repo: Path):
    commit_on_feature(repo, 'apps/svc/main.py', 'base\nmine\n')
    advance_main(repo, 'apps/svc/main.py', 'theirs\nbase\n')
    code, out = audit(repo)
    assert code == 1
    assert any('hot path' in line and 'REFUSED' in line for line in out)
    assert any(line == 'hot_overlap=1' for line in out)


def test_hot_paths_alone_do_not_block_when_the_base_left_them_untouched(repo: Path):
    """Touching apps/ is normal work. It only matters when the BASE touched it too —
    otherwise the old gate's hot-path signal was noise it printed and ignored anyway."""
    commit_on_feature(repo, 'apps/svc/main.py', 'mine\n')
    advance_main(repo, 'docs/notes.md', 'unrelated\n')
    code, out = audit(repo)
    assert code == 0, out
    assert any(line == 'hot_path_hits=1' for line in out)
    assert any(line == 'hot_overlap=0' for line in out)


def test_unbounded_drift_is_refused_even_without_overlap(repo: Path):
    commit_on_feature(repo, 'docs/notes.md', 'mine\n')
    for i in range(4):
        advance_main(repo, f'apps/other/f{i}.py', f'{i}\n', f'main {i}')
    code, out = audit(repo, max_behind=2)
    assert code == 1
    assert any('exceeds the 2 tolerance' in line for line in out)


def test_strict_mode_restores_the_old_behaviour_exactly(repo: Path):
    commit_on_feature(repo, 'docs/notes.md', 'mine\n')
    advance_main(repo, 'apps/other/thing.py', 'unrelated\n')
    assert audit(repo)[0] == 0, 'default: safe'
    code, out = audit(repo, strict=True)
    assert code == 1
    assert any('PREMERGE_STRICT=1' in line for line in out)


def test_a_branch_with_no_changes_is_a_no_op(repo: Path):
    code, out = audit(repo)
    assert code == 0
    assert any('nothing to audit' in line for line in out)


def test_report_always_carries_the_counters_downstream_tooling_reads(repo: Path):
    commit_on_feature(repo, 'docs/notes.md', 'mine\n')
    _, out = audit(repo)
    for key in ('changed_files=', 'ahead=', 'behind=', 'hot_path_hits=', 'overlap=', 'hot_overlap='):
        assert any(line.startswith(key) for line in out), f'missing {key}'


def test_strict_mode_fails_a_behind_branch_even_with_no_changes(repo: Path):
    """Regression (review-found): the old gate failed on `behind > 0` regardless of whether
    the branch changed anything. Strict mode must reproduce that exactly, so the no-op
    early return cannot be allowed to short-circuit it."""
    advance_main(repo, 'apps/other/thing.py', 'unrelated\n')
    code, out = audit(repo, strict=True)      # feature has NO commits of its own
    assert code == 1
    assert any('PREMERGE_STRICT=1' in line for line in out)
