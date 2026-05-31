import json
import subprocess
import sys
from pathlib import Path

import yaml


EXPECTED_OUTPUTS = {
    "run-record.json",
    "checksums.json",
    "validation-report.json",
    "benchmark-report.json",
    "sociosphere-registration.json",
    "sherlock-index-payload.json",
    "delivery-excellence-scoreboard-payload.json",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def fixture_manifest() -> Path:
    return repo_root() / "contracts" / "computational-artifacts" / "prophet-artifact.v1alpha1.example.yaml"


def validate_script() -> Path:
    return repo_root() / "tools" / "validate_prophet_artifact.py"


def runner_script() -> Path:
    return repo_root() / "tools" / "run_prophet_artifact.py"


def test_validate_fixture_manifest_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(validate_script()), "--artifact", str(fixture_manifest())],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert set(payload["supported_verbs"]) == {
        "detect",
        "fetch",
        "prepare",
        "build",
        "run",
        "validate",
        "benchmark",
        "tune",
        "publish",
        "attest",
    }


def test_missing_required_field_fails_closed_with_explicit_message(tmp_path: Path) -> None:
    manifest = yaml.safe_load(fixture_manifest().read_text(encoding="utf-8"))
    del manifest["metadata"]["version"]
    path = tmp_path / "missing-version.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=True), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(validate_script()), "--artifact", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "metadata.version is required" in result.stderr


def test_runner_emits_expected_evidence_bundle(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(runner_script()),
            "--artifact",
            str(fixture_manifest()),
            "--output-dir",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert EXPECTED_OUTPUTS <= {path.name for path in tmp_path.glob("*.json")}

    run_record = json.loads((tmp_path / "run-record.json").read_text(encoding="utf-8"))
    assert run_record["status"] == "succeeded"
    assert all(item["privileged"] is False for item in run_record["actions"])


def test_privileged_action_is_blocked_without_policy_flag(tmp_path: Path) -> None:
    manifest = yaml.safe_load(fixture_manifest().read_text(encoding="utf-8"))
    manifest["actions"][0]["privileged"] = True
    path = tmp_path / "privileged.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=True), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(runner_script()),
            "--artifact",
            str(path),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "is privileged and blocked" in result.stderr
    assert "--allow-privileged" in result.stderr
