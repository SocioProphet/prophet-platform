"""Adversarial tests for the path-filter auditor.

The auditor's whole value is that it FAILS when a filter stops covering its
inputs.  A checker that cannot fail is worse than no checker — it converts an
unverified assumption into a green tick.  So most of these tests deliberately
break something and assert the auditor notices.

Two of them exist because the auditor really did pass a broken filter during
development: `make <target>` hid the script in the Makefile, and
`pytest <dir>/` named a directory rather than a module, so in both cases the
auditor found nothing to analyse and vouched for a filter it had never read.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_workflow_path_filters.py"
WORKFLOWS = ROOT / ".github" / "workflows"

_spec = importlib.util.spec_from_file_location("cwpf", TOOL)
cwpf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cwpf)


def run_auditor() -> int:
    return subprocess.run([sys.executable, str(TOOL)], capture_output=True).returncode


@pytest.fixture
def mutate(tmp_path):
    """Edit a workflow in place, then restore it no matter how the test ends."""
    backups: list[tuple[Path, Path]] = []

    def _mutate(name: str, old: str, new: str = "") -> None:
        target = WORKFLOWS / name
        backup = tmp_path / name
        shutil.copy(target, backup)
        backups.append((target, backup))
        text = target.read_text(encoding="utf-8")
        assert old in text, f"fixture is stale: {old!r} not present in {name}"
        target.write_text(text.replace(old, new), encoding="utf-8")

    yield _mutate
    for target, backup in backups:
        shutil.copy(backup, target)


def test_repo_is_currently_clean():
    assert run_auditor() == 0, "vouched workflows must cover their inputs on main"


def test_narrowing_a_filter_is_caught(mutate):
    """Drop a validator's input dir from its filter -> the check would silently
    stop running on changes to that dir.  Must fail."""
    mutate("svf-validation.yml", "      - 'contracts/svf/**'\n")
    assert run_auditor() == 1


def test_narrowing_an_infra_filter_is_caught(mutate):
    """The defect this auditor found in its own author's work."""
    mutate("workspace-operation-runtime.yml", "      - 'infra/k8s/**'\n")
    assert run_auditor() == 1


def test_removing_the_push_on_main_safety_net_is_caught(mutate):
    """Without an unfiltered push-on-main trigger, a wrong filter means the
    validator never runs at all, rather than running late."""
    mutate("brokerage-validation.yml", "  push:\n    branches: [ main ]\n")
    assert run_auditor() == 1


def test_make_targets_are_resolved():
    """`run: make validate-svf-agent-contract` must resolve to the script the
    recipe actually invokes, or the workflow looks unanalysable."""
    assert "tools/validate_svf_agent_contract.py" in cwpf.make_target_scripts(
        "validate-svf-agent-contract")


def test_pytest_directories_are_resolved():
    """`pytest tests/workspace_operations/` names a directory, not a module."""
    found = cwpf.scripts_invoked("run: pytest tests/workspace_operations/ -q")
    assert any(f.startswith("tests/workspace_operations/") and f.endswith(".py")
               for f in found)


def test_unanalysable_vouched_workflow_fails(monkeypatch):
    """If we cannot see any script, we must not claim the filter is proven."""
    monkeypatch.setattr(cwpf, "scripts_invoked", lambda _text: set())
    assert cwpf.main() == 1


def test_double_star_glob_crosses_separators():
    """fnmatch's `*` stops at `/`; `a/**` must still match `a/b/c`."""
    assert cwpf.covered("infra/k8s/base/deploy.yaml", ["infra/k8s/**"])
    assert not cwpf.covered("infra/argocd/app.yaml", ["infra/k8s/**"])


def test_generated_artifacts_are_not_required_inputs():
    """A path the job itself writes under build/ is an output, not an input."""
    assert not any(p.startswith("build/") for p in cwpf.inputs_of(
        ROOT / "tools" / "check_workflow_path_filters.py"))


def test_multiline_run_block_scripts_are_seen():
    """A script invoked on line 2+ of a `run: |` block must be surfaced, or a
    vouched workflow could hide its real script from the auditor (Copilot on #1045)."""
    wf = (
        "name: x\non:\n  pull_request:\n    paths: ['tools/**']\n"
        "  push:\n    branches: [main]\njobs:\n  a:\n    steps:\n"
        "      - run: |\n"
        "          pip install foo\n"
        "          python3 tools/hidden_script.py\n"
        "          bash tools/another.sh\n"
    )
    found = cwpf.scripts_invoked(wf)
    assert "tools/hidden_script.py" in found
    assert "tools/another.sh" in found


@pytest.mark.parametrize("branches,expected", [
    ("[main]", True),
    ("[ main, dev ]", True),
    ('["main"]', True),
    ("[maintenance]", False),   # substring 'main' must NOT count as the main safety net
    ("[main-release]", False),
    ("[main/foo]", False),      # a slashed ref is a different branch, not `main`
    ("[main.*]", False),        # a glob is not the exact main-push safety net
    ("[dev, feature/main]", False),
])
def test_main_is_matched_as_a_whole_branch_token(branches, expected):
    wf = (f"name: y\non:\n  push:\n    branches: {branches}\n"
          f"  pull_request:\n    paths: ['x/**']\njobs: {{}}\n")
    assert cwpf.has_main_push(wf) is expected


@pytest.mark.parametrize("push_filter,expected", [
    ("", True),
    ("    paths: ['src/**']\n", False),
    ("    paths-ignore: ['docs/**']\n", False),   # paths-ignore still filters the push
])
def test_paths_ignore_push_is_not_an_unfiltered_safety_net(push_filter, expected):
    # A `paths-ignore:` push skips runs for the ignored set, so it cannot be the
    # unfiltered net that turns a wrong filter into merge-time detection.
    wf = (f"name: z\non:\n  push:\n    branches: [main]\n{push_filter}"
          f"jobs: {{}}\n")
    assert cwpf.has_main_push(wf) is expected
