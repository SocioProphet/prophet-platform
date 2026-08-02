"""Guards for the silent-pass defects closed in this change.

Each fix here removed a way for a check to report success without having verified
anything. An unguarded fix of that shape can regress just as silently as the original
defect, so these tests assert the *absence* of the silent-pass shape rather than the
presence of a feature.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"

# Validators whose entire signal comes from a glob. Each must refuse to pass on an empty
# match. The count is the floor that shipped when the guard was added.
GLOB_VALIDATORS = {
    "validate_adr_035_contracts.py": 5,
    "validate_device_orchestration.py": 5,
    "validate_helper_causal_receipts.py": 4,
    "validate_mutation_evidence.py": 3,
    "validate_proof_artifacts.py": 7,
    "validate_semantic_governance.py": 4,
    "validate_workroom_schemas.py": 2,
}


def _make_target_body(target: str) -> list[str]:
    """Return the recipe lines make actually associates with `target`."""
    lines = MAKEFILE.read_text(encoding="utf-8").splitlines()
    body: list[str] = []
    collecting = False
    for line in lines:
        if re.match(rf"^{re.escape(target)}:", line):
            collecting = True
            continue
        if collecting:
            if line.startswith("\t"):
                body.append(line[1:])
            elif line.strip() == "":
                continue
            else:
                break
    return body


# ── 1. an absent validator is a failure, not a skip ──────────────────────────────


def test_validate_repo_fails_when_a_validator_is_missing(tmp_path: Path) -> None:
    """Renaming a validator away must fail the gate rather than skip it."""
    source = (ROOT / "tools" / "validate_repo.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    dispatched = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "run_validator"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert dispatched, "validate_repo.py dispatches no validators — the scan is broken"

    # Every dispatched validator must exist. Absence is only legal with an explicit
    # OPTIONAL_VALIDATORS entry, which is what makes a deletion visible.
    allowlist = re.search(r"OPTIONAL_VALIDATORS: dict\[str, str\] = \{(.*?)\}", source, re.S)
    assert allowlist is not None, "OPTIONAL_VALIDATORS declaration not found"
    for rel in sorted(dispatched):
        if rel in allowlist.group(1):
            continue
        assert (ROOT / rel).exists(), (
            f"{rel} is dispatched by validate_repo.py but is not on disk, and has no "
            f"OPTIONAL_VALIDATORS entry explaining why"
        )


def test_missing_validator_is_not_silently_skipped() -> None:
    """The guard must fail closed: no exists() check that simply skips."""
    source = (ROOT / "tools" / "validate_repo.py").read_text(encoding="utf-8")
    assert "run_optional_validator" not in source, (
        "run_optional_validator returned silently when a validator file was absent; "
        "it must not come back"
    )
    assert "OPTIONAL_VALIDATORS" in source, "the explicit allowlist must remain the only skip path"
    assert "validator missing:" in source, "an absent validator must produce a named failure"


# ── 2. no `|| true` inside a required-gate leg ───────────────────────────────────


def test_lattice_studio_smoke_has_no_error_suppression() -> None:
    body = _make_target_body("lattice-studio-smoke")
    assert body, "lattice-studio-smoke target not found"
    offenders = [line for line in body if "|| true" in line]
    assert not offenders, (
        "lattice-studio-smoke feeds the required diagnostics-gate; `|| true` there turns a "
        f"failing step into a pass: {offenders}"
    )


def test_lattice_studio_smoke_asserts_its_own_outputs() -> None:
    """The `test -s` assertions must belong to the smoke target, not a stray target."""
    body = _make_target_body("lattice-studio-smoke")
    assertions = [line for line in body if line.startswith("test -s ")]
    assert len(assertions) >= 14, (
        f"expected the emitted-artifact assertions inside lattice-studio-smoke, found "
        f"{len(assertions)} — they were once orphaned into a bogus `test -s:` target and "
        f"never ran"
    )


def test_makefile_declares_no_bogus_test_target() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    assert not re.search(r"^test -s:", text, re.M), (
        "`test -s:` declares a make target named `test` with prerequisite `-s`; it silently "
        "swallowed the lattice-studio output assertions"
    )


# ── 3. an empty glob is a failure, not a pass ────────────────────────────────────


@pytest.mark.parametrize("filename,floor", sorted(GLOB_VALIDATORS.items()))
def test_glob_validator_declares_a_minimum_count(filename: str, floor: int) -> None:
    source = (ROOT / "tools" / filename).read_text(encoding="utf-8")
    match = re.search(r"^MIN_FIXTURES = (\d+)$", source, re.M)
    assert match is not None, (
        f"{filename} drives its checks from a glob but declares no MIN_FIXTURES floor, so an "
        f"empty match prints success having verified nothing"
    )
    declared = int(match.group(1))
    assert declared >= 1, f"{filename}: a floor of {declared} still permits an empty glob"
    assert declared == floor, (
        f"{filename}: MIN_FIXTURES is {declared}, expected {floor}. If fixtures were "
        f"deliberately added or removed, update this test in the same change."
    )
    assert "len(fixture_paths) < MIN_FIXTURES" in source, (
        f"{filename}: MIN_FIXTURES is declared but never compared against the glob result"
    )


@pytest.mark.parametrize("filename", sorted(GLOB_VALIDATORS))
def test_glob_validator_guard_precedes_the_loop(filename: str) -> None:
    """The count check must run before iteration, or it guards nothing."""
    source = (ROOT / "tools" / filename).read_text(encoding="utf-8")
    guard = source.index("len(fixture_paths) < MIN_FIXTURES")
    loop = source.index("for path in fixture_paths:")
    assert guard < loop, f"{filename}: the minimum-count guard runs after the loop"


@pytest.mark.parametrize("filename,floor", sorted(GLOB_VALIDATORS.items()))
def test_glob_validator_floor_matches_fixtures_on_disk(filename: str, floor: int) -> None:
    """The declared floor must not exceed what actually ships, or CI is red on arrival."""
    source = (ROOT / "tools" / filename).read_text(encoding="utf-8")
    match = re.search(r"^fixture_paths = sorted\((.+?)\.glob\((.+?)\)\)$", source, re.M)
    assert match is not None, f"{filename}: could not locate the materialised glob"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / filename)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{filename} fails against the fixtures on disk — MIN_FIXTURES={floor} may exceed "
        f"what ships:\n{result.stdout}\n{result.stderr}"
    )


# ── 4. checks that survive `python -O` ───────────────────────────────────────────


def test_liberty_stack_demo_check_survives_optimisation() -> None:
    """The readout check must fire under -O, where bare asserts are stripped."""
    tool = ROOT / "tools" / "test_liberty_stack_runtime_demo.py"
    source = tool.read_text(encoding="utf-8")
    tree = ast.parse(source)
    asserts = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    assert not asserts, (
        f"{tool.name} verifies the demo readout; bare asserts there vanish under `python -O` "
        f"(found {len(asserts)} on lines {[n.lineno for n in asserts]})"
    )
    assert "DemoCheckFailure" in source, "the readout check must raise explicitly"

    for args in ([sys.executable], [sys.executable, "-O"]):
        result = subprocess.run(
            [*args, str(tool)], cwd=ROOT, capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"{' '.join(args)} {tool.name} failed:\n{result.stdout}\n{result.stderr}"
        )
        assert '"ok": true' in result.stdout
