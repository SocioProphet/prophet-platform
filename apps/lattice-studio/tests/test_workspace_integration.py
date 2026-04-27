import json
from pathlib import Path

from lattice_studio.cli import main
from lattice_studio.platform_records import (
    platform_record_set,
    workspace_action_receipt_to_platform_record,
    workspace_source_binding_to_platform_record,
    workspace_source_to_platform_record,
    workspace_synthesis_artifact_to_platform_record,
)
from lattice_studio.workspace_flow import demo_workspace_flow

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_EXAMPLES = ROOT / "contracts" / "workspace"


def _fixture(name: str) -> dict:
    return json.loads((WORKSPACE_EXAMPLES / name).read_text(encoding="utf-8"))


def test_workspace_sources_convert_to_platform_records() -> None:
    docs = _fixture("workspace-source.document.json")
    sheet = _fixture("workspace-source.sheet.json")
    slide = _fixture("workspace-source.slide.json")

    records = [workspace_source_to_platform_record(doc) for doc in [docs, sheet, slide]]
    record_set = platform_record_set(records)

    assert record_set["kind"] == "PlatformAssetRecordSet"
    assert {record["assetKind"] for record in records} == {"workspace-docs", "workspace-sheets", "workspace-slides"}
    for record in records:
        assert record["producerRepo"] == "SocioProphet/prophet-workspace"
        assert "lattice-studio" in record["compatibilitySurfaces"]
        assert "prophet-workspace" in record["compatibilitySurfaces"]
        assert record["policyRef"] == "policy://workspace/demo"
        assert record["evidenceCorrelationId"].startswith("workspace-source:")


def test_workspace_action_receipt_converts_to_platform_record() -> None:
    receipt = _fixture("workspace-action-receipt.publish-report.json")
    record = workspace_action_receipt_to_platform_record(receipt)

    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "workspace-action-publish"
    assert record["producerRepo"] == "SocioProphet/prophet-workspace"
    assert record["policyRef"] == "policy://workspace/demo"
    assert record["evidenceCorrelationId"] == "workspace-action:publish/demo-report"
    assert "evidence-bundle" in record["compatibilitySurfaces"]


def test_workspace_sources_and_receipt_share_evidence_spine() -> None:
    sources = [
        _fixture("workspace-source.document.json"),
        _fixture("workspace-source.sheet.json"),
        _fixture("workspace-source.slide.json"),
    ]
    receipt = _fixture("workspace-action-receipt.publish-report.json")
    source_ids = {source["metadata"]["sourceId"] for source in sources}

    assert set(receipt["spec"]["inputSourceIds"]) == source_ids
    assert receipt["spec"]["runtimeAssetId"] == "runtime-asset:prophet-python-ml:0.1.0"
    assert receipt["spec"]["notebookSessionId"].startswith("notebook-session:")
    assert receipt["spec"]["outputDigest"].startswith("sha256:")


def test_workspace_flow_binds_sources_session_synthesis_and_receipt() -> None:
    flow = demo_workspace_flow()
    source_ids = {source["metadata"]["sourceId"] for source in flow["sources"]}
    session = flow["session"]
    binding = flow["binding"]
    synthesis = flow["synthesis"]
    evidence = flow["synthesisEvidence"]
    receipt = flow["receipt"]

    assert session["kind"] == "NotebookSession"
    assert set(session["catalogInputs"]) == source_ids
    assert binding["kind"] == "WorkspaceSourceBinding"
    assert set(binding["sourceIds"]) == source_ids
    assert binding["notebookSessionId"] == session["sessionId"]
    assert binding["runtimeAssetId"] == session["runtimeAssetId"]
    assert synthesis["kind"] == "WorkspaceSynthesisArtifact"
    assert set(synthesis["sourceIds"]) == source_ids
    assert synthesis["bindingId"] == binding["bindingId"]
    assert synthesis["notebookSessionId"] == session["sessionId"]
    assert evidence["kind"] == "WorkspaceSynthesisEvidence"
    assert evidence["artifactId"] == synthesis["artifactId"]
    assert evidence["bindingId"] == binding["bindingId"]
    assert evidence["notebookSessionId"] == session["sessionId"]
    assert evidence["runtimeAssetId"] == session["runtimeAssetId"]
    assert set(evidence["sourceIds"]) == source_ids
    assert evidence["artifactDigest"].startswith("sha256:")
    assert receipt["kind"] == "WorkspaceActionReceipt"
    assert set(receipt["spec"]["inputSourceIds"]) == source_ids
    assert receipt["spec"]["outputArtifactIds"] == [synthesis["artifactId"]]
    assert receipt["spec"]["outputDigest"] == evidence["artifactDigest"]


def test_workspace_binding_and_synthesis_convert_to_platform_records() -> None:
    flow = demo_workspace_flow()
    binding_record = workspace_source_binding_to_platform_record(flow["binding"])
    synthesis_record = workspace_synthesis_artifact_to_platform_record(flow["synthesis"])

    assert binding_record["assetKind"] == "workspace-source-binding"
    assert binding_record["assetId"] == flow["binding"]["bindingId"]
    assert "notebook-session" in binding_record["compatibilitySurfaces"]
    assert synthesis_record["assetKind"] == "workspace-synthesis-artifact"
    assert synthesis_record["assetId"] == flow["synthesis"]["artifactId"]
    assert "source-grounded-synthesis" in synthesis_record["compatibilitySurfaces"]
    assert "workspace-publication" in synthesis_record["compatibilitySurfaces"]


def test_cli_emits_workspace_demo_bundle(tmp_path) -> None:
    output_dir = tmp_path / "workspace-demo"
    rc = main(["emit-workspace-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    expected = {
        "workspace-source.docs_demo-brief.json",
        "workspace-source.sheets_demo-dataset.json",
        "workspace-source.slides_demo-report.json",
        "notebook-session.json",
        "workspace-source-binding.json",
        "workspace-synthesis-artifact.json",
        "workspace-synthesis-evidence.json",
        "workspace-action-receipt.publish-report.json",
        "workspace-platform-records.json",
    }
    assert expected == {path.name for path in output_dir.iterdir()}

    session = json.loads((output_dir / "notebook-session.json").read_text(encoding="utf-8"))
    binding = json.loads((output_dir / "workspace-source-binding.json").read_text(encoding="utf-8"))
    synthesis = json.loads((output_dir / "workspace-synthesis-artifact.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "workspace-synthesis-evidence.json").read_text(encoding="utf-8"))
    receipt = json.loads((output_dir / "workspace-action-receipt.publish-report.json").read_text(encoding="utf-8"))
    record_set = json.loads((output_dir / "workspace-platform-records.json").read_text(encoding="utf-8"))

    assert session["kind"] == "NotebookSession"
    assert binding["notebookSessionId"] == session["sessionId"]
    assert synthesis["bindingId"] == binding["bindingId"]
    assert evidence["artifactId"] == synthesis["artifactId"]
    assert receipt["spec"]["outputDigest"] == evidence["artifactDigest"]
    assert record_set["kind"] == "PlatformAssetRecordSet"
    assert len(record_set["records"]) == 7
    assert {record["assetKind"] for record in record_set["records"]} == {
        "workspace-docs",
        "workspace-sheets",
        "workspace-slides",
        "notebook-session",
        "workspace-source-binding",
        "workspace-synthesis-artifact",
        "workspace-action-publish",
    }
