"""The manifest's declared evidence must exist on disk, not merely be listed.

`require_set_contains()` proves the manifest *lists* a contract path. That is a
declaration about the world. Before this was pinned, every in-repo path named by
`workspaceOS.contractPaths` / `workspaceOS.controlRefs` could be deleted and the
validator would still print `OK: workspaceOS contract-aligned evidence present`
and exit 0 -- verified against the pre-fix tool.

These tests delete each declared path in turn and require a non-zero exit that
names it, under `python3` AND `python3 -O`. A check that has only ever been run
against a fully-present set has never been observed failing and proves nothing.

The expected paths below are written out literally rather than imported from the
tool. A test that derives its expectations from the code under test validates
nothing -- it agrees with whatever that code currently says.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "tools" / "validate_professional_intelligence_manifest.py"
MANIFEST_NAME = "professional-intelligence.manifest.yaml"

# The in-repo evidence the manifest claims contract alignment against. Held
# independently of the tool's own constants on purpose (see module docstring).
LOCAL_EVIDENCE = [
    "contracts/workspace/workroom-update-request.example.json",
    "contracts/workspace/workroom-update-response.accepted.example.json",
    "contracts/workspace/workroom-update-response.invalid-runtime-mutation.example.json",
    "docs/WORKROOM_UPDATE_RUNTIME_BOUNDARY.md",
    "tools/validate_workroom_update_contract.py",
]

# Refs into peer estate repos. These are not present in this checkout and so
# cannot be stat'd here; the tool must say so out loud rather than skip quietly.
CROSS_REPO_EVIDENCE = [
    "SocioProphet/prophet-workspace:contracts/workspace/workroom.schema.json",
    "SocioProphet/prophet-workspace:contracts/workspace/professional-workroom.schema.json",
    "SocioProphet/prophet-workspace:contracts/workspace/professional-workroom.v0.1.example.json",
    "SocioProphet/prophet-workspace:docs/workroom-substrate-alignment-v0.md",
    "SocioProphet/prophet-workspace:tools/validate_professional_workrooms.py",
    "SocioProphet/workspace-inventory:inventory/estate-overlays/prophet-workspace-workroom-substrate.yaml",
    "SocioProphet/systems-learning-loops:kb/receipts/prophet-workspace-workroom-substrate.receipt.yaml",
]

# Both interpreters must agree. `-O` strips asserts, so a check written as one
# evaporates there while still looking correct under a default test run.
INTERPRETERS = [
    pytest.param([sys.executable], id="python3"),
    pytest.param([sys.executable, "-O"], id="python3-O"),
]


def load_tool_module():
    spec = importlib.util.spec_from_file_location("_pi_manifest_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_root(tmp_path: Path) -> Path:
    """Materialise a synthetic repo root the tool will accept.

    The tool derives its ROOT from `Path(__file__).resolve().parents[1]`, so the
    tool is copied rather than symlinked -- a symlink resolves back to the real
    repo and would quietly validate the real tree instead of the fixture.
    """
    root = tmp_path / "root"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(TOOL, root / "tools" / TOOL.name)
    shutil.copy2(REPO_ROOT / MANIFEST_NAME, root / MANIFEST_NAME)
    for rel in LOCAL_EVIDENCE:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dest)
    return root


def run(root: Path, argv_prefix: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv_prefix + [str(root / "tools" / TOOL.name)],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_fixture_root_validates_and_the_existence_check_actually_ran(
    tmp_path: Path, argv_prefix: list[str]
) -> None:
    """Baseline: a complete tree passes, and the new check is observably live.

    Asserting rc==0 alone would also pass if the existence check were deleted,
    so this pins the evidence line too -- a checker must show it did the work,
    not merely print a success banner.
    """
    proc = run(build_root(tmp_path), argv_prefix)
    assert proc.returncode == 0, proc.stderr
    assert "workspaceOS.contractPaths: 3 in-repo evidence path(s) exist on disk" in proc.stdout
    assert "workspaceOS.controlRefs: 2 in-repo evidence path(s) exist on disk" in proc.stdout


@pytest.mark.parametrize("missing", LOCAL_EVIDENCE)
@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_deleting_a_declared_path_fails_and_names_it(
    tmp_path: Path, argv_prefix: list[str], missing: str
) -> None:
    """The teeth. Each declared path, deleted one at a time, must be caught."""
    root = build_root(tmp_path)
    (root / missing).unlink()

    proc = run(root, argv_prefix)
    assert proc.returncode == 2, f"deleting {missing} did not fail the validator: {proc.stdout}"
    assert missing in proc.stderr, proc.stderr
    assert "does not exist in this repo" in proc.stderr
    # The banner this gap used to reach must not be printed.
    assert "contract-aligned evidence present" not in proc.stdout


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_all_declared_paths_missing_is_reported_per_path(
    tmp_path: Path, argv_prefix: list[str]
) -> None:
    root = build_root(tmp_path)
    for rel in LOCAL_EVIDENCE:
        (root / rel).unlink()

    proc = run(root, argv_prefix)
    assert proc.returncode == 2, proc.stdout
    for rel in LOCAL_EVIDENCE:
        assert rel in proc.stderr, f"{rel} was not named in the failure output"


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_cross_repo_refs_are_skipped_out_loud(tmp_path: Path, argv_prefix: list[str]) -> None:
    """A silently-skipped ref is how declared-but-unverified evidence returns.

    Cross-repo refs genuinely cannot be stat'd from this checkout, so the tool
    must neither fail on them nor pass over them in silence.
    """
    proc = run(build_root(tmp_path), argv_prefix)
    assert proc.returncode == 0, proc.stderr
    assert "SKIP: workspaceOS.contractPaths: 3 cross-repo ref(s)" in proc.stdout
    assert "SKIP: workspaceOS.controlRefs: 4 cross-repo ref(s)" in proc.stdout
    for ref in CROSS_REPO_EVIDENCE:
        assert ref in proc.stdout, f"cross-repo ref {ref} was skipped without being named"
        # Skipped, not treated as a missing local file.
        assert ref not in proc.stderr


def test_cross_repo_classification_is_not_a_bare_colon_test() -> None:
    """Guard the partition itself: the skip list must not be able to grow silently.

    If a local path were misclassified as cross-repo it would be skipped rather
    than stat'd, quietly reopening the gap this file exists to close.
    """
    module = load_tool_module()
    for ref in CROSS_REPO_EVIDENCE:
        assert module.is_cross_repo_ref(ref), f"{ref} should be cross-repo"
    for ref in LOCAL_EVIDENCE:
        assert not module.is_cross_repo_ref(ref), f"{ref} should be checked locally"
    # A colon inside an ordinary in-repo path is not an estate ref.
    assert not module.is_cross_repo_ref("docs/notes:draft.md")
    # An unrecognised org must fall through to the LOCAL side, where it is
    # stat'd and fails loudly, rather than joining the silently-skipped column.
    # This is the safe direction for a misclassification and must stay that way.
    assert not module.is_cross_repo_ref("SomeOtherOrg/repo:contracts/thing.json")
    assert "SocioProphet" in module.ESTATE_ORGS

    declared = module.REQUIRED_WORKSPACE_OS_CONTRACTS | module.REQUIRED_WORKSPACE_OS_CONTROLS
    locally_checked = {r for r in declared if not module.is_cross_repo_ref(r)}
    assert locally_checked == set(LOCAL_EVIDENCE), (
        "the set of locally-verifiable evidence paths changed; update this test "
        "deliberately rather than letting a path drift into the skipped column"
    )


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_non_mapping_demo_acceptance_names_demo_acceptance(
    tmp_path: Path, argv_prefix: list[str]
) -> None:
    """A wrongly-shaped `demoAcceptance` must not be reported as `.required`.

    Diagnostics only -- both the old and new code fail closed with rc=2 -- but
    the old message pointed the reader at a field that was not the problem.
    """
    root = build_root(tmp_path)
    manifest = yaml.safe_load((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    manifest["demoAcceptance"] = ["workroom update contract validated"]
    (root / MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )

    proc = run(root, argv_prefix)
    assert proc.returncode == 2, proc.stdout
    assert "ERR: demoAcceptance must be a mapping/object" in proc.stderr
    assert "demoAcceptance.required" not in proc.stderr, (
        "the wrong field is still being named: " + proc.stderr
    )


@pytest.mark.parametrize("argv_prefix", INTERPRETERS)
def test_empty_demo_acceptance_required_still_names_required(
    tmp_path: Path, argv_prefix: list[str]
) -> None:
    """The correct diagnosis for the correct fault is unchanged."""
    root = build_root(tmp_path)
    manifest = yaml.safe_load((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    manifest["demoAcceptance"] = {"required": []}
    (root / MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )

    proc = run(root, argv_prefix)
    assert proc.returncode == 2, proc.stdout
    assert "ERR: demoAcceptance.required must be a non-empty list" in proc.stderr
