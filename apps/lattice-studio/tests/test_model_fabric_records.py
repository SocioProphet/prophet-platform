import json
from pathlib import Path

import pytest

from lattice_studio.model_fabric_records import (
    MODEL_FABRIC_SURFACES,
    functional_service_registry_to_model_fabric_record_set,
    functional_service_to_model_fabric_record,
)

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "contracts" / "modality" / "functional-service-registry.v1.example.json"


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_functional_service_registry_emits_model_fabric_record_set() -> None:
    record_set = functional_service_registry_to_model_fabric_record_set(_registry())

    assert record_set["apiVersion"] == "prophet.socioprophet.dev/v1"
    assert record_set["kind"] == "PlatformAssetRecordSet"
    records = record_set["records"]
    assert {record["assetKind"] for record in records} == {
        "model-fabric-routing",
        "model-fabric-guardrail",
        "model-fabric-model-governance",
        "model-fabric-agent-registry",
    }
    assert {record["modelFabric"]["sourceosCarryPolicy"]["role"] for record in records} == {"carry-only"}
    assert {record["modelFabric"]["sourceosCarryPolicy"]["mayPromoteModel"] for record in records} == {False}
    assert {record["modelFabric"]["sourceosCarryPolicy"]["mayReplaceServiceArtifact"] for record in records} == {False}


def test_model_fabric_records_include_expected_source_repos_and_surfaces() -> None:
    record_set = functional_service_registry_to_model_fabric_record_set(_registry())
    by_kind = {record["assetKind"]: record for record in record_set["records"]}

    assert "SocioProphet/model-router" in by_kind["model-fabric-routing"]["compatibilitySurfaces"]
    assert "SocioProphet/guardrail-fabric" in by_kind["model-fabric-guardrail"]["compatibilitySurfaces"]
    assert "SocioProphet/model-governance-ledger" in by_kind["model-fabric-model-governance"]["compatibilitySurfaces"]
    assert "SocioProphet/agent-registry" in by_kind["model-fabric-agent-registry"]["compatibilitySurfaces"]
    for surface in MODEL_FABRIC_SURFACES:
        assert any(surface in record["compatibilitySurfaces"] for record in record_set["records"])


def test_model_fabric_record_rejects_sourceos_mutable_model_authority() -> None:
    service = next(
        service
        for service in _registry()["spec"]["services"]
        if service["surface"] == "routing"
    )
    bad = json.loads(json.dumps(service))
    bad["sourceosCarryPolicy"]["mayPromoteModel"] = True

    with pytest.raises(ValueError, match="must not promote"):
        functional_service_to_model_fabric_record(bad)


def test_model_fabric_record_rejects_non_fabric_surface() -> None:
    service = next(
        service
        for service in _registry()["spec"]["services"]
        if service["surface"] == "language"
    )

    with pytest.raises(ValueError, match="not a model-fabric surface"):
        functional_service_to_model_fabric_record(service)
