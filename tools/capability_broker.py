#!/usr/bin/env python3
"""Deterministic capability broker (Workspace Control Plane, Phase 2 / D7).

Resolves a requested capability across sources in a FIXED order — local
manifests -> local affordances -> MCP servers -> trusted catalogs -> remote
joins — applying trust gates (signed, unexpired, unrevoked, catalog-listed) from
a DiscoveryPolicy, and emitting a provenance `event.v0` for every resolution.

This is a controlled 'go fish': the planner never crawls arbitrarily. Sources,
policy, and catalogs all conform to the Phase-1 frozen schemas.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# The deterministic lane order the policy may sequence over.
LANES = ["local_manifest", "local_affordance", "mcp_server", "trusted_catalog", "remote_join"]


@dataclass
class Source:
    """A discovery source: a lane label plus a capability manifest."""

    lane: str
    manifest: dict[str, Any]


@dataclass
class ResolutionResult:
    """Outcome of a resolve() call."""

    resolved: bool
    capability: str
    lane: Optional[str] = None
    provider: Optional[str] = None
    manifest_id: Optional[str] = None
    rejected: list[dict[str, str]] = field(default_factory=list)
    event: dict[str, Any] = field(default_factory=dict)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def trust_reason(manifest: dict[str, Any], policy: dict[str, Any], now: str,
                 trusted_ids: Optional[set[str]] = None, lane: str = "") -> Optional[str]:
    """Return a rejection reason if the manifest fails the trust gate, else None."""
    req = policy.get("trust_requirements", {})
    if req.get("require_signed") and not manifest.get("signature"):
        return "unsigned"
    expiry = manifest.get("expiry")
    if expiry and _parse(expiry) <= _parse(now):
        return "expired"
    revocation = manifest.get("revocation")
    if req.get("require_revocation_check"):
        if revocation is None:
            return "no_revocation_field"
        if revocation.get("revoked"):
            return "revoked"
    elif revocation and revocation.get("revoked"):
        return "revoked"
    # Catalog gating: a manifest surfaced via a trusted catalog must be listed.
    if lane == "trusted_catalog" and trusted_ids is not None:
        if manifest.get("manifest_id") not in trusted_ids:
            return "not_in_trusted_catalog"
    return None


def _catalog_trusted_ids(catalogs: list[dict[str, Any]], now: str) -> set[str]:
    """The set of manifest ids trusted via valid catalog entries."""
    ids: set[str] = set()
    for entry in catalogs:
        exp = entry.get("expiry")
        if exp and _parse(exp) <= _parse(now):
            continue
        if not entry.get("signatures"):
            continue
        deleg = entry.get("delegation") or {}
        threshold = deleg.get("threshold")
        if threshold is not None and len(entry.get("signatures", [])) < threshold:
            continue
        ids.update(entry.get("targets", []))
    return ids


def _provides(manifest: dict[str, Any], capability: str) -> bool:
    return any(c.get("name") == capability for c in manifest.get("capabilities", []))


def resolve(
    capability: str,
    sources: list[Source],
    policy: dict[str, Any],
    *,
    catalogs: Optional[list[dict[str, Any]]] = None,
    now: Optional[str] = None,
) -> ResolutionResult:
    """Resolve `capability` deterministically per `policy.resolution_order`."""
    now = now or datetime.now(timezone.utc).isoformat()
    catalogs = catalogs or []
    trusted_ids = _catalog_trusted_ids(catalogs, now)
    rejected: list[dict[str, str]] = []

    for lane in policy.get("resolution_order", []):
        for src in sources:
            if src.lane != lane:
                continue
            if not _provides(src.manifest, capability):
                continue
            reason = trust_reason(src.manifest, policy, now, trusted_ids, lane)
            if reason is not None:
                rejected.append({"manifest_id": src.manifest.get("manifest_id", "?"), "lane": lane, "reason": reason})
                continue
            provider = src.manifest.get("provider", "")
            mid = src.manifest.get("manifest_id", "")
            return ResolutionResult(
                resolved=True, capability=capability, lane=lane, provider=provider,
                manifest_id=mid, rejected=rejected,
                event=_event("CapabilityResolved", capability, now,
                             object_refs=[mid], outputs={"lane": lane, "provider": provider}),
            )

    return ResolutionResult(
        resolved=False, capability=capability, rejected=rejected,
        event=_event("CapabilityUnresolved", capability, now, object_refs=[],
                     outputs={"rejected": rejected}),
    )


def _event(activity: str, capability: str, now: str, *, object_refs: list[str],
           outputs: dict[str, Any]) -> dict[str, Any]:
    """A provenance event.v0 for a resolution (append-only, object-centric)."""
    return {
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "ts": now,
        "case_id": f"capability-resolution/{capability}",
        "activity": activity,
        "actor": "capability-broker",
        "object_refs": object_refs,
        "inputs": {"capability": capability},
        "outputs": outputs,
        "prov": {"activity": activity, "agent": "capability-broker"},
    }
