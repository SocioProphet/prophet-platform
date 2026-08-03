"""The `effect-discipline` entry's probe_cmd in docs/design-register.yaml (Copilot #1004/#1016).

The bug this suite exists to prevent recurring: the probe_cmd claimed to verify "the gateway
test dir is CI-gated (enforcement = app-test-diagnostics runs the whole suite)", but the command
itself was `grep -rq "compute-gateway" .github/workflows/` — satisfied by ANY workflow file that
so much as mentions the string "compute-gateway" (a Docker image build, a secret-provisioning
step, ...), none of which run pytest. A probe that "validates X" but runs a command that doesn't
touch X can stay green forever, including in the exact scenario it exists to catch: the CI step
that actually runs the law suite being deleted while an unrelated job still name-drops the
service. Every case below asserts the register's OWN probe_cmd, run for real via subprocess
(the same way tools/design_register_gate.py runs it), not a reimplementation of it.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = REPO_ROOT / "docs" / "design-register.yaml"


def _probe_cmd(entry_id: str) -> str:
    doc = yaml.safe_load(REGISTER.read_text())
    for e in doc["register"]:
        if e["id"] == entry_id:
            cmd = e.get("probe_cmd")
            assert cmd, f"{entry_id} has no probe_cmd"
            return cmd
    raise AssertionError(f"no entry {entry_id!r} in the register")


def _make_repo(tmp_path: Path, *, ci_runs_the_law_suite: bool) -> Path:
    (tmp_path / "apps/compute-gateway/tests").mkdir(parents=True)
    (tmp_path / "apps/compute-gateway/tests/test_receipt_compositionality.py").write_text("# law suite\n")
    wf = tmp_path / ".github/workflows"
    wf.mkdir(parents=True)
    if ci_runs_the_law_suite:
        (wf / "validate-target-diagnostics.yml").write_text(textwrap.dedent("""\
            jobs:
              app-test-diagnostics:
                strategy:
                  matrix:
                    include:
                      - name: compute-gateway
                        working-directory: apps/compute-gateway
                        install: pip install -r requirements.txt pytest
                        test: PYTHONPATH=src pytest -q tests
            """))
    else:
        # "compute-gateway" appears — but only in a job that builds a Docker image and never
        # runs the test suite. A bare-substring probe cannot tell this apart from real CI gating.
        (wf / "images.yml").write_text(textwrap.dedent("""\
            jobs:
              build:
                strategy:
                  matrix:
                    include:
                      - { image: compute-gateway, context: apps/compute-gateway, dockerfile: Dockerfile }
            """))
    return tmp_path


def _run(cmd: str, cwd: Path) -> int:
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True).returncode


def test_probe_fails_when_ci_no_longer_runs_the_law_suite(tmp_path):
    """The regression this probe exists to catch. If it stays green here, it gates nothing."""
    cmd = _probe_cmd("effect-discipline")
    repo = _make_repo(tmp_path, ci_runs_the_law_suite=False)
    assert _run(cmd, repo) != 0


def test_probe_passes_when_ci_genuinely_runs_the_law_suite(tmp_path):
    cmd = _probe_cmd("effect-discipline")
    repo = _make_repo(tmp_path, ci_runs_the_law_suite=True)
    assert _run(cmd, repo) == 0


def test_probe_fails_when_the_law_suite_file_itself_is_missing(tmp_path):
    repo = _make_repo(tmp_path, ci_runs_the_law_suite=True)
    (repo / "apps/compute-gateway/tests/test_receipt_compositionality.py").unlink()
    assert _run(_probe_cmd("effect-discipline"), repo) != 0


def test_probe_passes_against_the_real_repo_at_head():
    """Sanity: the register isn't currently lying about main."""
    assert _run(_probe_cmd("effect-discipline"), REPO_ROOT) == 0
