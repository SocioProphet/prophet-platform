import json

from lattice_studio.placement_decision import (
    demo_placement_dry_run_report,
    placement_dry_run_evidence,
    placement_dry_run_to_platform_record,
)
from lattice_studio.placement_decision_cli import main


def test_placement_dry_run_report_passes_required_checks() -> None:
    report = demo_placement_dry_run_report()
    doc = report.to_dict()

    assert doc["kind"] == "PlacementDryRunReport"
    assert doc["status"] == "pass"
    checks = {check["name"]: check for check in doc["checks"]}
    assert checks["byoc-compute-targets"]["status"] == "pass"
    assert checks["byoc-storage-targets"]["status"] == "pass"
    assert checks["byoc-io-bindings"]["status"] == "pass"
    assert checks["cloudshell-fog-terminal-path"]["status"] == "pass"
    assert checks["m2-topolvm-safety-boundary"]["status"] == "pass"
    assert checks["notebook-adapter-launch-coverage"]["status"] == "pass"
    assert checks["promotion-target-coverage"]["status"] == "pass"
    assert "no-cluster-apply" in doc["sideEffectBoundary"]
    assert "dry-run-only" in doc["sideEffectBoundary"]


def test_placement_dry_run_evidence_and_platform_record() -> None:
    report = demo_placement_dry_run_report()
    evidence = placement_dry_run_evidence(report)
    record = placement_dry_run_to_platform_record(report)

    assert evidence["kind"] == "PlacementDryRunEvidence"
    assert evidence["status"] == "pass"
    assert evidence["checkCount"] == 7
    assert "cloudshell-fog-terminal-path" in evidence["evidenceReports"]
    assert "m2-topolvm-safety-boundary" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "placement-dry-run-report"
    assert "cloudshell-fog" in record["compatibilitySurfaces"]
    assert "notebook-promotion" in record["compatibilitySurfaces"]


def test_placement_decision_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "placement"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    report = json.loads((output_dir / "placement-dry-run-report.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "placement-dry-run-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "placement-dry-run-platform-record.json").read_text(encoding="utf-8"))

    assert report["kind"] == "PlacementDryRunReport"
    assert evidence["kind"] == "PlacementDryRunEvidence"
    assert record["kind"] == "PlatformAssetRecord"
