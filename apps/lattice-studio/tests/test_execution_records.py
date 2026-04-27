import json

from lattice_studio.cli import main
from lattice_studio.execution import demo_execution_record, execution_evidence, execution_to_platform_record


def test_demo_execution_record_links_inputs_outputs_runtime_session_paas_and_atlas() -> None:
    execution = demo_execution_record()
    doc = execution.to_dict()
    evidence = execution_evidence(execution)
    record = execution_to_platform_record(execution)

    assert doc["kind"] == "ExecutionRecord"
    assert doc["executionKind"] == "notebook-run"
    assert doc["status"] == "succeeded"
    assert doc["runtimeAssetId"] == "runtime-asset:prophet-python-ml:0.1.0"
    assert doc["notebookSessionId"] == "notebook-session:demo1234567890abcd"
    assert doc["paasDeploymentId"] == "paas-deployment:demo1234567890"
    assert doc["atlasContextId"] == "atlas-context:demo1234567890ab"
    assert "catalog://datasets/demo-csv@0.1.0" in doc["inputAssetRefs"]
    assert "catalog://services/demo-inference-service@0.1.0" in doc["outputAssetRefs"]
    assert "used" in doc["lineagePredicates"]
    assert "generated" in doc["lineagePredicates"]
    assert evidence["kind"] == "ExecutionEvidence"
    assert evidence["executionDigest"].startswith("sha256:")
    assert "lineage-predicates" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "execution-notebook-run"
    assert "execution-lineage" in record["compatibilitySurfaces"]


def test_cli_emits_execution_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "execution"
    rc = main(["emit-execution", "--output-dir", str(output_dir)])
    assert rc == 0

    execution = json.loads((output_dir / "execution-record.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "execution-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "execution-platform-record.json").read_text(encoding="utf-8"))

    assert execution["kind"] == "ExecutionRecord"
    assert evidence["kind"] == "ExecutionEvidence"
    assert record["kind"] == "PlatformAssetRecord"
