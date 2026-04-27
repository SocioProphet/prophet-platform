import json
from pathlib import Path

from lattice_studio.platform_records import (
    platform_record_set,
    workspace_action_receipt_to_platform_record,
    workspace_source_to_platform_record,
)

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_EXAMPLES = ROOT.parent / "prophet-workspace" / "examples"


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
