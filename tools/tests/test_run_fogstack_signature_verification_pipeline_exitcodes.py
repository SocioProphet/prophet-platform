from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("tools/run_fogstack_signature_verification_pipeline.py")


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def base_manifest() -> dict[str, object]:
    return {
        "kind": "FogStackBundleManifest",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "bundle_digest": "sha256:abc123",
        "signature": {"ref": "oci://example/fogstack.access.sig"},
    }


def run_pipeline(tmp_path: Path, evidence: dict[str, object]) -> subprocess.CompletedProcess[str]:
    manifest = tmp_path / "manifest.json"
    raw = tmp_path / "cosign.json"
    record = tmp_path / "record.json"
    write_json(manifest, base_manifest())
    write_json(raw, evidence)

    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--external-evidence",
            str(raw),
            "--out",
            str(record),
        ],
        text=True,
        capture_output=True,
    )


def test_signature_pipeline_success_emits_verified_record(tmp_path: Path) -> None:
    proc = run_pipeline(tmp_path, {"status": "pass", "verified_digest": "sha256:abc123"})
    assert proc.returncode == 0, proc.stdout + proc.stderr

    record = json.loads((tmp_path / "record.json").read_text(encoding="utf-8"))
    assert record["status"] == "verified"
    assert record["summary"]["manifest_digest_matches"] is True


def test_signature_pipeline_digest_mismatch_fails_hard(tmp_path: Path) -> None:
    proc = run_pipeline(tmp_path, {"status": "pass", "verified_digest": "sha256:wrong"})
    assert proc.returncode == 2

    record = json.loads((tmp_path / "record.json").read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert record["summary"]["status"] == "fail"
    assert record["summary"]["manifest_digest_matches"] is False


def test_signature_pipeline_malformed_input_returns_invalid(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    raw = tmp_path / "broken.json"
    write_json(manifest, base_manifest())
    raw.write_text("{not-json", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--external-evidence",
            str(raw),
            "--out",
            str(tmp_path / "record.json"),
        ],
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 3
    assert not (tmp_path / "record.json").exists()


def test_signature_pipeline_warning_returns_one(tmp_path: Path) -> None:
    proc = run_pipeline(tmp_path, {"status": "warn", "verified_digest": "sha256:abc123"})
    assert proc.returncode == 1

    record = json.loads((tmp_path / "record.json").read_text(encoding="utf-8"))
    assert record["status"] == "shape-only"
    assert record["summary"]["manifest_digest_matches"] is True


def test_signature_pipeline_raw_evidence_alias_still_works(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    raw = tmp_path / "cosign.json"
    record = tmp_path / "record.json"
    write_json(manifest, base_manifest())
    write_json(raw, {"status": "pass", "verified_digest": "sha256:abc123"})

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--raw-evidence",
            str(raw),
            "--record-output",
            str(record),
        ],
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(record.read_text(encoding="utf-8"))["status"] == "verified"
