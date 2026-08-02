"""Test the New Hope + Slash Topics integration validator against the landed tree."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools" / "validate_newhope_slashtopics_integration.py"

# Import the module directly (not via the package) so `confine()` is testable in
# isolation, the same way the validator itself is invoked as a standalone script.
_spec = importlib.util.spec_from_file_location("validate_newhope_slashtopics_integration", VALIDATOR)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
confine = _mod.confine


def test_validator_passes_on_landed_tree():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"validator failed (rc={result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "all checks passed" in result.stdout.lower()


def test_mirrored_schemas_and_examples_present():
    specs = ROOT / "contracts" / "imported" / "slash-topics" / "specs"
    examples = ROOT / "examples" / "newhope-slash-topics"
    for name in (
        "SlashTopics_Schema_v0.1.json",
        "Membrane_Decision_v0.1.json",
        "Membrane_Decision_v0.2.json",
        "Model_Selection_Policy_v0.1.json",
    ):
        assert (specs / name).is_file(), f"missing mirrored schema: {name}"
    assert (examples / "slash_topics_pack_min.example.json").is_file()
    assert (examples / "membrane_decision_allow.example.json").is_file()


# ── confine(): the path-traversal/absolute-escape guard must actually be able to fail ──
# A validator whose own safety property is unenforced is exactly the "declared, never
# checked" defect this estate's controls exist to catch. These prove `confine()` raises
# on every escape shape a crafted IMPORT_MANIFEST.yaml entry could carry, not just that
# it's silent on the happy path (which a no-op implementation would also satisfy).

def test_confine_allows_a_genuine_relative_subpath(tmp_path):
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "x.json").write_text("{}")
    resolved = confine(tmp_path, "specs/x.json")
    assert resolved == (tmp_path / "specs" / "x.json").resolve()


def test_confine_rejects_an_absolute_path():
    with pytest.raises(ValueError, match="absolute"):
        confine(Path("/tmp/some-base"), "/etc/passwd")


def test_confine_rejects_dotdot_traversal_out_of_base(tmp_path):
    outside = tmp_path.parent / "outside-marker.txt"
    outside.write_text("should never be reachable")
    try:
        with pytest.raises(ValueError, match="outside"):
            confine(tmp_path, f"../{outside.name}")
    finally:
        outside.unlink()


def test_confine_rejects_dotdot_that_only_partially_escapes_then_returns(tmp_path):
    # A path that dips outside base and back in (e.g. 'a/../../base_name/x') must still
    # be judged on its FINAL resolved location, not on whether it happens to land back
    # inside — but if the final resolution truly is outside base.parent entirely, reject.
    sibling = tmp_path.parent / "sibling_dir"
    sibling.mkdir(exist_ok=True)
    try:
        with pytest.raises(ValueError, match="outside"):
            confine(tmp_path, f"../{sibling.name}/x.json")
    finally:
        sibling.rmdir()


def test_confine_allows_absolute_only_when_explicitly_opted_in(tmp_path):
    target = tmp_path / "x.json"
    target.write_text("{}")
    # Without opt-in, absolute is rejected (proven above). With explicit opt-in it is
    # accepted but STILL confined to base — an absolute path outside base still fails.
    assert confine(tmp_path, str(target), allow_absolute=True) == target.resolve()
    with pytest.raises(ValueError, match="outside"):
        confine(tmp_path, "/etc/passwd", allow_absolute=True)


def test_validator_fails_closed_on_a_traversal_manifest(tmp_path, monkeypatch):
    # End-to-end: point the validator's IMPORT_MANIFEST at a crafted copy whose
    # slash-topics local_path escapes ROOT via traversal, and confirm the validator
    # itself exits non-zero with a clear [FAIL] — not a stack trace, not a silent pass.
    import shutil

    fake_root = tmp_path / "fake_repo"
    shutil.copytree(ROOT, fake_root, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    manifest_path = fake_root / "contracts" / "imported" / "IMPORT_MANIFEST.yaml"
    text = manifest_path.read_text(encoding="utf-8")
    poisoned = text.replace(
        "local_path: contracts/imported/slash-topics/",
        "local_path: ../../../../../../etc",
    )
    assert poisoned != text, "fixture assumption broke: the local_path line moved or was renamed"
    manifest_path.write_text(poisoned, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(fake_root / "tools" / "validate_newhope_slashtopics_integration.py")],
        capture_output=True,
        text=True,
        cwd=fake_root,
    )
    assert result.returncode != 0, "a traversal local_path was accepted instead of rejected"
    assert "[FAIL]" in result.stderr, f"rejected without the tool's own [FAIL] message:\n{result.stderr}"
    assert "outside" in result.stderr.lower(), f"rejection reason doesn't mention the escape:\n{result.stderr}"
