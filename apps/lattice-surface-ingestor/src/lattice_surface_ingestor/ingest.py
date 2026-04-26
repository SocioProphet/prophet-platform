"""Normalize Lattice product-surface handoff objects into platform assets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlatformAssetRecord:
    """Normalized record emitted by the side-effect-free ingestor."""

    asset_id: str
    asset_kind: str
    name: str
    version: str
    source_api_version: str
    source_kind: str
    producer_repo: str
    policy_ref: str | None
    evidence_correlation_id: str | None
    promotion_channel: str | None
    compatibility_surfaces: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "prophet.socioprophet.dev/v1",
            "kind": "PlatformAssetRecord",
            "assetId": self.asset_id,
            "assetKind": self.asset_kind,
            "name": self.name,
            "version": self.version,
            "sourceApiVersion": self.source_api_version,
            "sourceKind": self.source_kind,
            "producerRepo": self.producer_repo,
            "policyRef": self.policy_ref,
            "evidenceCorrelationId": self.evidence_correlation_id,
            "promotionChannel": self.promotion_channel,
            "compatibilitySurfaces": self.compatibility_surfaces,
        }


def ingest_surface(doc: dict[str, Any]) -> PlatformAssetRecord:
    """Dispatch a supported handoff object into a normalized platform asset."""

    kind = doc.get("kind")
    if kind == "BootReleaseSet":
        return ingest_boot_release_set(doc)
    if kind == "RuntimeAsset":
        return ingest_runtime_asset(doc)
    raise ValueError(f"unsupported lattice surface kind: {kind!r}")


def ingest_boot_release_set(doc: dict[str, Any]) -> PlatformAssetRecord:
    metadata = _required_dict(doc, "metadata")
    spec = _required_dict(doc, "spec")
    evidence = _required_dict(spec, "evidence")
    name = _required_str(metadata, "name")
    version = _required_str(metadata, "version")
    return PlatformAssetRecord(
        asset_id=f"boot-release-set:{name}:{version}",
        asset_kind="boot-release-set",
        name=name,
        version=version,
        source_api_version=_required_str(doc, "apiVersion"),
        source_kind="BootReleaseSet",
        producer_repo="SourceOS-Linux/sourceos-boot",
        policy_ref=spec.get("releaseSetRef"),
        evidence_correlation_id=evidence.get("correlationId"),
        promotion_channel=None,
        compatibility_surfaces=["sourceos-boot", "prophet-platform"],
    )


def ingest_runtime_asset(doc: dict[str, Any]) -> PlatformAssetRecord:
    metadata = _required_dict(doc, "metadata")
    spec = _required_dict(doc, "spec")
    promotion = _required_dict(spec, "promotion")
    compatibility = _required_dict(spec, "compatibility")
    name = _required_str(metadata, "name")
    version = _required_str(metadata, "version")
    surfaces = compatibility.get("surfaces", [])
    if not isinstance(surfaces, list):
        raise ValueError("RuntimeAsset compatibility.surfaces must be a list")
    return PlatformAssetRecord(
        asset_id=f"runtime-asset:{name}:{version}",
        asset_kind="runtime-asset",
        name=name,
        version=version,
        source_api_version=_required_str(doc, "apiVersion"),
        source_kind="RuntimeAsset",
        producer_repo="SocioProphet/lattice-forge",
        policy_ref=None,
        evidence_correlation_id=None,
        promotion_channel=promotion.get("channel"),
        compatibility_surfaces=[str(surface) for surface in surfaces],
    )


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value
