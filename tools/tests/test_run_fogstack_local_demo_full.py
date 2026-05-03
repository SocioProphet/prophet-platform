from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED_FULL_ARTIFACTS = {
    "local_demo_summary",
    "local_demo_markdown",
    "local_demo_html",
    "artifact_index",
    "deploy_summary",
    "deploy_plan",
    "agent_corps_plan",
    "kubernetes_configmap",
    "kubernetes_deployment",
    "kubernetes_service",
    "kubernetes_manifest_check_record",
}


def test_run_fogstack_local_demo_full(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_fogstack_local_demo_full.py",
            "--output-dir",
            str(output_dir),
            "--summary",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "FogStack full local demo passed." in proc.stdout
    assert "Artifact index:" in proc.stdout
    assert "Deploy plan:" in proc.stdout
    assert "Kubernetes deployment:" in proc.stdout

    full_summary_path = output_dir / "fogstack-local-demo.full.summary.json"
    assert full_summary_path.exists()
    full_summary = json.loads(full_summary_path.read_text(encoding="utf-8"))
    assert full_summary["kind"] == "FogStackLocalDemoFullRun"
    assert full_summary["status"] == "passed"
    assert REQUIRED_FULL_ARTIFACTS == set(full_summary["artifacts"])
    for ref in full_summary["artifacts"].values():
        assert Path(ref).exists(), ref

    artifact_index = json.loads((output_dir / "demo-artifacts.index.json").read_text(encoding="utf-8"))
    indexed_ids = {entry["id"] for entry in artifact_index["artifacts"]}
    assert "deploy_plan" in indexed_ids
    assert "deploy_kubernetes_deployment" in indexed_ids
    assert "deploy_kubernetes_manifest_check_record" in indexed_ids

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Deploy readiness" in html
    assert "SHA-256 digest" in html
    assert "indexed" in html
    assert "deploy_plan" in html
    assert "fogstack.access.deploy-plan.json" in html
