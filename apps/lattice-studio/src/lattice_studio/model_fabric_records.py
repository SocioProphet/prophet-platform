"""Emit PlatformAssetRecord objects for model-fabric services.

This module projects entries from the functional service registry into the
canonical platform-record spine used by Lattice Studio and Prophet Platform.
It is intentionally registry-only: it does not invoke model routers, guardrail
evaluators, ledgers, agent registries, or live provider services.
"""

from __future__ import annotations

from typing import Any

from .platform_records import platform_record_set

MODEL_FABRIC_SURFACES = {"routing", "guardrail", "model-governance", "agent-registry"}


def functional_service_to_model_fabric_record(service: dict[str, Any]) -> dict[str, Any]:
    """Convert one functional service registry entry into a PlatformAssetRecord."""
    service_id = _required_str(service, "serviceId")
    surface = _required_str(service, "surface")
    status = _required_str(service, "status")
    source_repos = _required_list(service, "sourceRepos")
    evidence_requirements = _required_list(service, "evidenceRequirements")
    promotion = _required_dict(service, "promotion")
    carry = _required_dict(service, "sourceosCarryPolicy")

    if surface not in MODEL_FABRIC_SURFACES:
        raise ValueError(f"service surface {surface!r} is not a model-fabric surface")
    if carry.get("role") != "carry-only":
        raise ValueError("sourceosCarryPolicy.role must be carry-only")
    if carry.get("mayReplaceServiceArtifact") is not False:
        raise ValueError("SourceOS must not replace model-fabric service artifacts")
    if carry.get("mayPromoteModel") is not False:
        raise ValueError("SourceOS must not promote model-fabric models")

    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": service_id,
        "assetKind": f"model-fabric-{surface}",
        "name": _name_from_service_id(service_id),
        "version": _version_from_service_id(service_id),
        "sourceApiVersion": "modality.socioprophet.dev/v1",
        "sourceKind": "FunctionalServiceRegistryService",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": carry.get("role"),
        "evidenceCorrelationId": service_id,
        "promotionChannel": promotion.get("state") or status,
        "compatibilitySurfaces": [
            "lattice-studio",
            "prophet-platform",
            "functional-model-surfaces",
            "model-fabric",
            surface,
            *source_repos,
        ],
        "modelFabric": {
            "serviceStatus": status,
            "sourceRepos": source_repos,
            "evidenceRequirements": evidence_requirements,
            "rollbackRef": _required_str(promotion, "rollbackRef"),
            "sourceosCarryPolicy": carry,
        },
    }


def functional_service_registry_to_model_fabric_record_set(registry: dict[str, Any]) -> dict[str, Any]:
    """Convert model-fabric services from a registry into a PlatformAssetRecordSet."""
    if registry.get("apiVersion") != "modality.socioprophet.dev/v1":
        raise ValueError("registry apiVersion must be modality.socioprophet.dev/v1")
    if registry.get("kind") != "FunctionalServiceRegistry":
        raise ValueError("registry kind must be FunctionalServiceRegistry")
    services = registry.get("spec", {}).get("services", [])
    if not isinstance(services, list):
        raise ValueError("registry spec.services must be a list")
    records = [
        functional_service_to_model_fabric_record(service)
        for service in services
        if isinstance(service, dict) and service.get("surface") in MODEL_FABRIC_SURFACES
    ]
    return platform_record_set(records)


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _required_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} must be a non-empty list")
    return value


def _version_from_service_id(service_id: str) -> str:
    if "@" not in service_id:
        return "0.1.0"
    return service_id.rsplit("@", 1)[1]


def _name_from_service_id(service_id: str) -> str:
    without_scheme = service_id.removeprefix("service://")
    without_version = without_scheme.rsplit("@", 1)[0]
    return without_version.replace("/", "-")
