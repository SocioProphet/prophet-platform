"""Model-fabric runtime adapter contract fixtures.

These adapters describe how Prophet Platform will bind model-fabric backing
services. They are contract fixtures only. They do not invoke provider APIs,
execute models, mutate ledgers, or grant agent authority.
"""

from __future__ import annotations

from typing import Any

REQUIRED_SURFACES = {"routing", "guardrail", "model-governance", "agent-registry"}
REQUIRED_BOUNDARIES = {"no-secret-material", "sourceos-carry-only"}


def validate_model_fabric_adapter_set(adapter_set: dict[str, Any]) -> dict[str, Any]:
    if adapter_set.get("apiVersion") != "modelfabric.socioprophet.dev/v1":
        raise ValueError("adapter set apiVersion must be modelfabric.socioprophet.dev/v1")
    if adapter_set.get("kind") != "ModelFabricRuntimeAdapterSet":
        raise ValueError("adapter set kind must be ModelFabricRuntimeAdapterSet")
    adapters = adapter_set.get("spec", {}).get("adapters", [])
    if not isinstance(adapters, list) or not adapters:
        raise ValueError("adapter set spec.adapters must be a non-empty list")

    seen_ids: set[str] = set()
    surfaces: set[str] = set()
    for idx, adapter in enumerate(adapters):
        _validate_adapter(adapter, idx)
        adapter_id = adapter["adapterId"]
        if adapter_id in seen_ids:
            raise ValueError(f"duplicate adapterId: {adapter_id}")
        seen_ids.add(adapter_id)
        surfaces.add(adapter["surface"])
    missing = sorted(REQUIRED_SURFACES - surfaces)
    if missing:
        raise ValueError(f"missing model-fabric adapter surfaces: {missing}")
    return adapter_set


def summarize_model_fabric_adapter_set(adapter_set: dict[str, Any]) -> dict[str, Any]:
    validate_model_fabric_adapter_set(adapter_set)
    adapters = adapter_set["spec"]["adapters"]
    return {
        "apiVersion": "modelfabric.socioprophet.dev/v1",
        "kind": "ModelFabricRuntimeAdapterSummary",
        "adapterCount": len(adapters),
        "surfaces": sorted({adapter["surface"] for adapter in adapters}),
        "serviceRefs": sorted(adapter["serviceRef"] for adapter in adapters),
        "mode": sorted({adapter["mode"] for adapter in adapters}),
        "boundary": sorted(set().union(*(set(adapter["boundary"]) for adapter in adapters))),
    }


def _validate_adapter(adapter: dict[str, Any], idx: int) -> None:
    prefix = f"adapters[{idx}]"
    required = {
        "adapterId",
        "serviceRef",
        "surface",
        "mode",
        "commandRef",
        "inputRefs",
        "outputRefs",
        "evidenceRefs",
        "policyRefs",
        "boundary",
    }
    missing = sorted(required - set(adapter))
    if missing:
        raise ValueError(f"{prefix} missing fields: {missing}")
    if not str(adapter["adapterId"]).startswith("adapter://"):
        raise ValueError(f"{prefix}.adapterId must be an adapter:// ref")
    if not str(adapter["serviceRef"]).startswith("service://"):
        raise ValueError(f"{prefix}.serviceRef must be a service:// ref")
    if adapter["surface"] not in REQUIRED_SURFACES:
        raise ValueError(f"{prefix}.surface is not a known model-fabric surface")
    if adapter["mode"] != "contract-fixture":
        raise ValueError(f"{prefix}.mode must be contract-fixture")
    for list_field in ["inputRefs", "outputRefs", "evidenceRefs", "policyRefs", "boundary"]:
        value = adapter[list_field]
        if not isinstance(value, list) or not value:
            raise ValueError(f"{prefix}.{list_field} must be a non-empty list")
    boundaries = set(adapter["boundary"])
    missing_boundary = sorted(REQUIRED_BOUNDARIES - boundaries)
    if missing_boundary:
        raise ValueError(f"{prefix}.boundary missing required boundaries: {missing_boundary}")
    if adapter["surface"] == "model-governance" and "no-ledger-mutation" not in boundaries:
        raise ValueError(f"{prefix}.boundary must include no-ledger-mutation")
    if adapter["surface"] == "agent-registry" and "no-authority-grant" not in boundaries:
        raise ValueError(f"{prefix}.boundary must include no-authority-grant")
