import json

from lattice_studio.m2_topolvm import (
    demo_m2_topolvm_placement_plan,
    m2_topolvm_evidence,
    m2_topolvm_to_platform_record,
)
from lattice_studio.m2_topolvm_cli import main


def test_m2_topolvm_plan_binds_sourceos_registry_to_local_k8s_pool() -> None:
    plan = demo_m2_topolvm_placement_plan()
    doc = plan.to_dict()

    assert doc["kind"] == "M2TopoLVMPlacementPlan"
    assert doc["mode"] == "inception-agent-cluster"
    assert doc["clusterRef"] == "k8s://local-inception/demo"
    assert doc["nodePoolRef"] == "k8s-nodepool://local-vm/topolvm-agents"
    assert len(doc["topolvmClaims"]) == 2
    assert {claim["storageClass"] for claim in doc["topolvmClaims"]} == {"topolvm-provisioner"}
    assert doc["m2RegistryMount"]["proofIndexRef"] == "contracts/sourceos/examples/proof-index.m2-demo.v0.json"
    assert "proof-index.json" in doc["m2RegistryMount"]["mountedArtifacts"]
    assert "ontogenesis:Platform/Inception.ttl#MinIO" in doc["inceptionRefs"]
    assert "no-host-mutation" in doc["safetyBoundary"]
    assert "topolvm-mount-dry-run" in doc["safetyBoundary"]


def test_m2_topolvm_evidence_and_platform_record() -> None:
    plan = demo_m2_topolvm_placement_plan()
    evidence = m2_topolvm_evidence(plan)
    record = m2_topolvm_to_platform_record(plan)

    assert evidence["kind"] == "M2TopoLVMEvidence"
    assert evidence["claimCount"] == 2
    assert evidence["mountedArtifactCount"] == 7
    assert "sourceos-m2-filesystem-registry" in evidence["evidenceReports"]
    assert "inception-agent-cluster-binding" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "m2-topolvm-placement-plan"
    assert "topolvm" in record["compatibilitySurfaces"]
    assert "inception-agent-cluster" in record["compatibilitySurfaces"]


def test_m2_topolvm_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "m2-topolvm"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    plan = json.loads((output_dir / "m2-topolvm-placement-plan.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "m2-topolvm-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "m2-topolvm-platform-record.json").read_text(encoding="utf-8"))

    assert plan["kind"] == "M2TopoLVMPlacementPlan"
    assert evidence["kind"] == "M2TopoLVMEvidence"
    assert record["kind"] == "PlatformAssetRecord"
