"""Test the New Hope + Slash Topics integration validator against the landed tree."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools" / "validate_newhope_slashtopics_integration.py"


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
