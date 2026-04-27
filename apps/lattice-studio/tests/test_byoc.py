import json

from lattice_studio.byoc import byoc_evidence, byoc_to_platform_record, demo_byoc_placement_plan
from lattice_studio.byoc_cli import main


def test_byoc_plan_covers_storage_compute_io_and_cloudshell_fog() -> None:
    plan = demo_byoc_placement_plan()
    doc = plan.to_dict()

    assert doc["kind"] == "BYOCPlacementPlan"
    assert len(doc["storageProfiles"]) == 2
    assert {profile["kind"] for profile in doc["storageProfiles"]} == {"s3-compatible", "posix"}
    assert len(doc["computeTargets"]) == 3
    assert {target["kind"] for target in doc["computeTargets"]} == {"kubernetes", "array-cluster", "local-sourceos"}
    assert len(doc["ioBindings"]) == 3
    assert {binding["kind"] for binding in doc["ioBindings"]} == {"object-store", "websocket-pty"}
    assert doc["cloudShellFog"]["repoRef"] == "SocioProphet/cloudshell-fog"
    assert doc["cloudShellFog"]["placementMode"] == "fog-first-cloud-fallback"
    assert "websocket-pty" in doc["cloudShellFog"]["capabilities"]
    assert "tekton-chains-supply-chain" in doc["cloudShellFog"]["capabilities"]


def test_byoc_evidence_and_platform_record() -> None:
    plan = demo_byoc_placement_plan()
    evidence = byoc_evidence(plan)
    record = byoc_to_platform_record(plan)

    assert evidence["kind"] == "BYOCPlacementEvidence"
    assert evidence["storageProfileCount"] == 2
    assert evidence["computeTargetCount"] == 3
    assert evidence["ioBindingCount"] == 3
    assert "fog-first-terminal-placement" in evidence["evidenceReports"]
    assert "websocket-pty-binding" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "byoc-placement-plan"
    assert "cloudshell-fog" in record["compatibilitySurfaces"]
    assert "array-cluster" in record["compatibilitySurfaces"]


def test_byoc_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "byoc"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    plan = json.loads((output_dir / "byoc-placement-plan.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "byoc-placement-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "byoc-platform-record.json").read_text(encoding="utf-8"))

    assert plan["kind"] == "BYOCPlacementPlan"
    assert evidence["kind"] == "BYOCPlacementEvidence"
    assert record["kind"] == "PlatformAssetRecord"
