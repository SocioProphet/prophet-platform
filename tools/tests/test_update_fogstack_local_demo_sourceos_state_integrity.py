from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_update_fogstack_local_demo_sourceos_state_integrity(tmp_path: Path) -> None:
    summary_path = tmp_path / "fogstack-local-demo.full.summary.json"
    artifact_index_path = tmp_path / "demo-artifacts.index.json"
    report_path = tmp_path / "sourceos.state-integrity-report.json"

    summary_path.write_text(
        json.dumps(
            {
                "kind": "FogStackLocalDemoFullRun",
                "schema_version": "v0.1",
                "status": "passed",
                "artifacts": {},
                "checks": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    artifact_index_path.write_text(
        json.dumps(
            {
                "kind": "FogStackLocalDemoArtifactIndex",
                "schema_version": "v0.1",
                "artifacts": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "tools/update_fogstack_local_demo_sourceos_state_integrity.py",
            "--summary-json",
            str(summary_path),
            "--artifact-index",
            str(artifact_index_path),
            "--output",
            str(report_path),
            "--summary",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "SourceOS state integrity report:" in proc.stdout
    assert "FogStack full summary updated:" in proc.stdout
    assert "Artifact index updated:" in proc.stdout

    report = load(report_path)
    assert report["schema"] == "sourceos.state-integrity-report/v1alpha1"
    assert report["identity"]["component"] == "sourceos-syncd"
    assert report["identity"]["repo"] == "github://SourceOS-Linux/sourceos-syncd"
    assert report["collection"]["status"] == "complete"
    assert report["pipeline"]["mode"] == "bounded-local-demo"
    assert report["pipeline"]["mutating_repairs_enabled"] is False
    assert report["diagnosis"]["status"] == "healthy"
    assert report["attestation"]["artifact_indexed"] is True

    summary = load(summary_path)
    assert summary["artifacts"]["sourceos_state_integrity_report"] == str(report_path)
    assert "sourceos_state_integrity_report_indexed" in summary["checks"]

    index = load(artifact_index_path)
    entries = index["artifacts"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["id"] == "sourceos_state_integrity_report"
    assert entry["ref"] == str(report_path)
    assert entry["digest"].startswith("sha256:")
    assert len(entry["digest"]) == 71
    assert entry["size_bytes"] == report_path.stat().st_size
