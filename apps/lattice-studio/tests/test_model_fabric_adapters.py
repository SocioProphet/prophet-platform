import json
from pathlib import Path

import pytest

from lattice_studio.model_fabric_adapters import (
    REQUIRED_SURFACES,
    summarize_model_fabric_adapter_set,
    validate_model_fabric_adapter_set,
)

ROOT = Path(__file__).resolve().parents[3]
ADAPTER_SET = ROOT / "contracts" / "model-fabric" / "runtime-adapter-set.example.json"


def _adapter_set() -> dict:
    return json.loads(ADAPTER_SET.read_text(encoding="utf-8"))


def test_model_fabric_adapter_set_validates() -> None:
    adapter_set = validate_model_fabric_adapter_set(_adapter_set())

    assert adapter_set["kind"] == "ModelFabricRuntimeAdapterSet"
    assert {adapter["surface"] for adapter in adapter_set["spec"]["adapters"]} == REQUIRED_SURFACES


def test_model_fabric_adapter_summary_covers_required_boundaries() -> None:
    summary = summarize_model_fabric_adapter_set(_adapter_set())

    assert summary["kind"] == "ModelFabricRuntimeAdapterSummary"
    assert summary["adapterCount"] == 4
    assert set(summary["surfaces"]) == REQUIRED_SURFACES
    assert set(summary["mode"]) == {"contract-fixture"}
    assert "no-secret-material" in summary["boundary"]
    assert "sourceos-carry-only" in summary["boundary"]
    assert "no-authority-grant" in summary["boundary"]
    assert "no-ledger-mutation" in summary["boundary"]


def test_model_fabric_adapter_set_rejects_missing_surface() -> None:
    adapter_set = _adapter_set()
    adapter_set["spec"]["adapters"] = [
        adapter for adapter in adapter_set["spec"]["adapters"] if adapter["surface"] != "agent-registry"
    ]

    with pytest.raises(ValueError, match="missing model-fabric adapter surfaces"):
        validate_model_fabric_adapter_set(adapter_set)


def test_model_fabric_adapter_set_rejects_authority_grant_boundary_violation() -> None:
    adapter_set = _adapter_set()
    agent = next(adapter for adapter in adapter_set["spec"]["adapters"] if adapter["surface"] == "agent-registry")
    agent["boundary"] = [item for item in agent["boundary"] if item != "no-authority-grant"]

    with pytest.raises(ValueError, match="no-authority-grant"):
        validate_model_fabric_adapter_set(adapter_set)
