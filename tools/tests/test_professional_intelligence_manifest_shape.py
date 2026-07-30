"""The manifest shape guards must reject malformed input under `python -O` too.

`python -O` strips every `assert`, so a validator whose shape checks are bare
asserts reports success on input it never validated. This tool used to carry
three such asserts (on the manifest, on `capabilities`, and on
`capabilities.workspaceOS`). They were removable rather than convertible: each
sat immediately after an `expect_mapping()` guard that already rejects a
non-mapping, prints ERR and drives a non-zero exit -- a plain isinstance test,
not an assert, so -O leaves it intact.

These tests pin that. They run the validator under BOTH interpreters and
require identical, failing behaviour on each malformed shape, so the guards
cannot silently regress into assert-based checking -- which would still look
correct under a default `python3` test run and fail open under -O.
"""

from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "tools" / "validate_professional_intelligence_manifest.py"
MANIFEST_NAME = "professional-intelligence.manifest.yaml"

# Both interpreters must agree. Under -O the tool is what CI would run if
# PYTHONOPTIMIZE were ever set in the environment; the point of the pair is
# that the two columns never diverge.
INTERPRETERS = [
    pytest.param([sys.executable], id="python3"),
    pytest.param([sys.executable, "-O"], id="python3-O"),
]


def real_manifest() -> dict:
    return yaml.safe_load((REPO_ROOT / MANIFEST_NAME).read_text(encoding="utf-8"))


def run_against(tmp_path: Path, manifest_obj: object, argv_prefix: list[str]):
    """Run the validator against a synthetic repo root holding `manifest_obj`.

    The tool resolves its own location (`Path(__file__).resolve().parents[1]`)
    to find the manifest, so the tool is copied -- a symlink would resolve back
    to the real repo and quietly validate the real manifest instead.
    """
    root = tmp_path / "root"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(TOOL, root / "tools" / TOOL.name)
    (root / MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest_obj, sort_keys=False), encoding="utf-8"
    )
    return subprocess.run(
        argv_prefix + [str(root / "tools" / TOOL.name)],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_real_manifest_still_validates(tmp_path: Path, argv_prefix: list[str]) -> None:
    """A checker that rejects valid input is worse than the bug it fixed."""
    proc = run_against(tmp_path, real_manifest(), argv_prefix)
    assert proc.returncode == 0, proc.stderr
    assert "structure valid" in proc.stdout


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_non_mapping_manifest_is_rejected(tmp_path: Path, argv_prefix: list[str]) -> None:
    proc = run_against(tmp_path, [{"apiVersion": "x"}, {"kind": "y"}], argv_prefix)
    assert proc.returncode == 2, proc.stdout
    assert "manifest must be a mapping/object" in proc.stderr
    # Must not have reached the success banner.
    assert "structure valid" not in proc.stdout


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_non_mapping_capabilities_is_rejected(tmp_path: Path, argv_prefix: list[str]) -> None:
    manifest = real_manifest()
    manifest["capabilities"] = ["workspaceOS", "institutionGraph"]
    proc = run_against(tmp_path, manifest, argv_prefix)
    assert proc.returncode == 2, proc.stdout
    assert "capabilities must be a mapping/object" in proc.stderr
    assert "structure valid" not in proc.stdout


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_non_mapping_workspace_os_is_rejected(tmp_path: Path, argv_prefix: list[str]) -> None:
    manifest = real_manifest()
    manifest["capabilities"] = copy.deepcopy(manifest["capabilities"])
    manifest["capabilities"]["workspaceOS"] = ["status", "ownerRepos"]
    proc = run_against(tmp_path, manifest, argv_prefix)
    assert proc.returncode == 2, proc.stdout
    assert "capabilities.workspaceOS must be a mapping/object" in proc.stderr
    assert "structure valid" not in proc.stdout


def test_validator_carries_no_bare_asserts() -> None:
    """Guard the guard: no shape check in this tool may be a bare `assert`.

    Catches a regression at the source rather than only through behaviour --
    if someone reintroduces `assert isinstance(...)` here, -O would strip it.
    """
    import ast

    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    asserts = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    assert not asserts, f"{TOOL.name} regained bare assert(s) at line(s) {asserts}"
