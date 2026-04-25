import json
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_validator(*args: str) -> subprocess.CompletedProcess[str]:
    script = repo_root() / "tools" / "validate_prophet_operations_policy_decisions.py"
    return subprocess.run([sys.executable, str(script), *args], text=True, capture_output=True)


def bundle_path() -> Path:
    return repo_root() / "examples" / "operations" / "prophet_operations_evidence_bundle_with_policy_decision_links_0001.json"


def manual_review_decision_path() -> Path:
    return repo_root() / "examples" / "operations" / "prophet_operations_action_decision_manual_review_0001.json"


def allow_decision_path() -> Path:
    return repo_root() / "examples" / "operations" / "prophet_operations_action_decision_allow_0001.json"


def test_manual_review_decision_blocks_execution_without_failing_non_executable_validation():
    result = run_validator("--bundle", str(bundle_path()), "--decision", str(manual_review_decision_path()))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["summary"]["blocked_count"] == 1
    assert report["summary"]["executable_count"] == 0
    assert report["blocked_recommendations"] == [
        {"recommendation_id": "oprec-worker-1-isolate", "outcome": "manual_review"}
    ]


def test_manual_review_decision_fails_when_executable_action_is_required():
    result = run_validator(
        "--bundle",
        str(bundle_path()),
        "--decision",
        str(manual_review_decision_path()),
        "--require-executable",
    )
    assert result.returncode != 0
    assert "decision outcome=manual_review" in result.stderr


def test_missing_decision_fails_when_executable_action_is_required():
    result = run_validator("--bundle", str(bundle_path()), "--require-executable")
    assert result.returncode != 0
    assert "requires policy decision but no matching decision artifact" in result.stderr


def test_allow_decision_passes_when_executable_action_is_required():
    result = run_validator(
        "--bundle",
        str(bundle_path()),
        "--decision",
        str(allow_decision_path()),
        "--require-executable",
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["summary"]["blocked_count"] == 0
    assert report["summary"]["executable_count"] == 1
    assert report["executable_recommendations"] == ["oprec-worker-1-isolate"]


def test_invalid_decision_shape_fails_policy_fabric_schema_validation(tmp_path: Path):
    invalid = json.loads(allow_decision_path().read_text(encoding="utf-8"))
    del invalid["basis"]
    invalid_path = tmp_path / "invalid_decision.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

    result = run_validator("--bundle", str(bundle_path()), "--decision", str(invalid_path))

    assert result.returncode != 0
    assert "failed Policy Fabric schema validation" in result.stderr
    assert "basis" in result.stderr
