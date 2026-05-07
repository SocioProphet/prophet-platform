from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


class SocialEnvironmentError(ValueError):
    """Raised when social-environment analysis cannot be produced."""


def social_environment_snapshot(
    *,
    cell_id: str,
    peers: list[dict[str, Any]],
    interactions: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    feedback_events: list[dict[str, Any]],
    now: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic SocioSphere-facing social-environment snapshot.

    This snapshot is deliberately transparent and heuristic. It does not claim
    final social truth; it creates a governed, auditable feature surface for
    SocioSphere, reputation, and policy review.
    """

    if not cell_id:
        raise SocialEnvironmentError("cell_id is required")
    now_dt = _parse_time(now or _now())
    peer_ids = [peer.get("peer_ref") or peer.get("id") for peer in peers if peer.get("peer_ref") or peer.get("id")]
    peer_set = set(peer_ids)
    interactions_by_peer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for interaction in interactions:
        peer_ref = interaction.get("peer_ref")
        if peer_ref:
            interactions_by_peer[peer_ref].append(interaction)

    stale_ties = []
    for peer_ref in peer_ids:
        latest = _latest_time([item.get("observed_at") or item.get("created_at") for item in interactions_by_peer.get(peer_ref, [])])
        if latest is None:
            continue  # No interactions recorded; treat as new, not stale.
        if (now_dt - latest).days >= 30:
            stale_ties.append(peer_ref)

    communities = Counter(peer.get("community_ref", "community://unknown") for peer in peers)
    emerging_communities = [community for community, count in communities.items() if community != "community://unknown" and count >= 2]

    noisy_targets = _attention_sinks(feedback_events, signals)
    amplification_flags = coordinated_amplification_flags(interactions=interactions, signals=signals)

    return {
        "cell_id": cell_id,
        "snapshot_at": now_dt.isoformat().replace("+00:00", "Z"),
        "peer_count": len(peer_set),
        "stale_tie_count": len(stale_ties),
        "emerging_community_count": len(emerging_communities),
        "attention_sink_count": len(noisy_targets),
        "coordinated_amplification_flags": amplification_flags,
        "stale_ties": sorted(stale_ties),
        "emerging_communities": sorted(emerging_communities),
        "attention_sinks": noisy_targets,
        "relationship_hygiene": relationship_hygiene_recommendations(stale_ties=stale_ties, attention_sinks=noisy_targets),
    }


def reputation_delta_event(
    *,
    cell_id: str,
    subject_ref: str,
    subject_kind: str,
    context: str,
    evidence_refs: list[str],
    feedback_events: list[dict[str, Any]],
    interactions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a contextual reputation delta with anti-manipulation signals."""

    if not cell_id or not subject_ref or not subject_kind:
        raise SocialEnvironmentError("cell_id, subject_ref, and subject_kind are required")
    if subject_kind not in {"human", "agent", "source", "model", "workflow", "community", "claim"}:
        raise SocialEnvironmentError(f"unsupported subject_kind: {subject_kind}")
    if not evidence_refs:
        raise SocialEnvironmentError("reputation events require evidence_refs")

    positive = sum(1 for event in feedback_events if event.get("action") in {"follow", "mark_relevant", "promote_source", "save", "share"})
    negative = sum(1 for event in feedback_events if event.get("action") in {"mark_irrelevant", "delete", "mute_source", "dismiss"})
    total = positive + negative
    raw_delta = 0.0 if total == 0 else (positive - negative) / max(total, 1)
    anti = anti_manipulation_assessment(subject_ref=subject_ref, evidence_refs=evidence_refs, interactions=interactions)
    adjusted_delta = raw_delta * anti["provenance_weight"] * anti["anti_gaming_weight"]
    low, high = confidence_interval(adjusted_delta, evidence_count=len(evidence_refs), observation_count=max(total, len(interactions)))

    return {
        "cell_id": cell_id,
        "subject_ref": subject_ref,
        "subject_kind": subject_kind,
        "context": context,
        "evidence_refs": evidence_refs,
        "delta": round(adjusted_delta, 4),
        "decay_policy": "time_decay:half_life_90d",
        "dispute_state": "none",
        "policy_effect": reputation_policy_effect(adjusted_delta, anti),
        "anti_manipulation": anti,
        "confidence_interval": {"low": low, "high": high},
        "score_components": {
            "trust": round(max(0.0, adjusted_delta), 4),
            "authority": round(_component_score(interactions, "authority"), 4),
            "popularity": round(_component_score(interactions, "popularity"), 4),
            "expertise": round(_component_score(interactions, "expertise"), 4),
        },
        "event_at": _now(),
    }


def anti_manipulation_assessment(*, subject_ref: str, evidence_refs: list[str], interactions: list[dict[str, Any]]) -> dict[str, Any]:
    actors = [item.get("actor_ref") for item in interactions if item.get("actor_ref")]
    unique_actors = set(actors)
    claim_refs = [item.get("claim_ref") for item in interactions if item.get("claim_ref")]
    claim_counts = Counter(claim_refs)
    repeated_claims = sorted(claim for claim, count in claim_counts.items() if claim and count >= 3)
    sybil_score = 0.0 if not actors else 1.0 - (len(unique_actors) / len(actors))
    collusion_score = min(1.0, len(repeated_claims) / 3)
    provenance_weight = min(1.0, 0.35 + 0.15 * len(set(evidence_refs)))
    anti_gaming_weight = max(0.1, 1.0 - max(sybil_score, collusion_score) * 0.75)
    flags = []
    if sybil_score >= 0.5:
        flags.append("possible_sybil_repetition")
    if collusion_score > 0:
        flags.append("coordinated_claim_amplification")
    if provenance_weight < 0.6:
        flags.append("weak_provenance")
    return {
        "subject_ref": subject_ref,
        "sybil_score": round(sybil_score, 4),
        "collusion_score": round(collusion_score, 4),
        "provenance_weight": round(provenance_weight, 4),
        "anti_gaming_weight": round(anti_gaming_weight, 4),
        "flags": flags,
        "repeated_claim_refs": repeated_claims,
    }


def coordinated_amplification_flags(*, interactions: list[dict[str, Any]], signals: list[dict[str, Any]]) -> list[str]:
    claim_counts = Counter(item.get("claim_ref") for item in interactions if item.get("claim_ref"))
    flags = [f"claim:{claim}:count:{count}" for claim, count in sorted(claim_counts.items()) if claim and count >= 3]
    evidence_counts = Counter(ref for signal in signals for ref in signal.get("evidence_refs", []))
    flags.extend(f"evidence:{ref}:count:{count}" for ref, count in sorted(evidence_counts.items()) if count >= 3)
    return flags


def relationship_hygiene_recommendations(*, stale_ties: list[str], attention_sinks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations = []
    for peer_ref in stale_ties:
        recommendations.append({"action": "review_stale_tie", "target_ref": peer_ref, "reason": "no recent interaction inside freshness window"})
    for sink in attention_sinks:
        recommendations.append({"action": "mute_or_refine", "target_ref": sink["target_ref"], "reason": sink["reason"]})
    return recommendations


def social_snapshot_fact(snapshot: dict[str, Any]) -> dict[str, Any]:
    required = ["cell_id", "snapshot_at", "peer_count", "stale_tie_count", "emerging_community_count", "attention_sink_count", "coordinated_amplification_flags"]
    _require(snapshot, required)
    return {
        "cell_id": snapshot["cell_id"],
        "snapshot_at": snapshot["snapshot_at"],
        "peer_count": int(snapshot["peer_count"]),
        "stale_tie_count": int(snapshot["stale_tie_count"]),
        "emerging_community_count": int(snapshot["emerging_community_count"]),
        "attention_sink_count": int(snapshot["attention_sink_count"]),
        "coordinated_amplification_flags": snapshot.get("coordinated_amplification_flags", []),
        "body": snapshot,
    }


def reputation_delta_fact(event: dict[str, Any]) -> dict[str, Any]:
    _require(event, ["cell_id", "subject_ref", "subject_kind", "context", "delta", "confidence_interval", "anti_manipulation", "event_at"])
    interval = event["confidence_interval"]
    anti = event["anti_manipulation"]
    return {
        "cell_id": event["cell_id"],
        "subject_ref": event["subject_ref"],
        "subject_kind": event["subject_kind"],
        "context": event["context"],
        "delta": float(event["delta"]),
        "confidence_low": float(interval["low"]),
        "confidence_high": float(interval["high"]),
        "anti_manipulation_flags": anti.get("flags", []),
        "event_at": event["event_at"],
    }


def source_quality_fact(*, cell_id: str, source_id: str, source_kind: str, event_at: str, feedback_events: list[dict[str, Any]], signals: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = sum(1 for event in feedback_events if event.get("action") in {"follow", "mark_relevant", "promote_source", "save", "share"})
    rejected = sum(1 for event in feedback_events if event.get("action") in {"mark_irrelevant", "delete", "dismiss"})
    muted = sum(1 for event in feedback_events if event.get("action") == "mute_source")
    promoted = sum(1 for event in feedback_events if event.get("action") == "promote_source")
    relevance_values = [float(signal.get("relevance_score", 0.0)) for signal in signals if signal.get("source_id") == source_id]
    confidence_values = [float(signal.get("confidence_score", 0.0)) for signal in signals if signal.get("source_id") == source_id]
    return {
        "cell_id": cell_id,
        "source_id": source_id,
        "source_kind": source_kind,
        "event_at": event_at,
        "relevance_mean": round(sum(relevance_values) / len(relevance_values), 4) if relevance_values else 0.0,
        "confidence_mean": round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else 0.0,
        "accepted_count": accepted,
        "rejected_count": rejected,
        "muted_count": muted,
        "promoted_count": promoted,
    }


def confidence_interval(delta: float, *, evidence_count: int, observation_count: int) -> tuple[float, float]:
    width = max(0.05, 0.5 / max(1, evidence_count + observation_count))
    return (round(max(-1.0, delta - width), 4), round(min(1.0, delta + width), 4))


def reputation_policy_effect(delta: float, anti: dict[str, Any]) -> str:
    if anti.get("flags"):
        return "review_required"
    if delta >= 0.5:
        return "increase_trust"
    if delta <= -0.5:
        return "decrease_trust"
    return "observe"


def _attention_sinks(feedback_events: list[dict[str, Any]], signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signal_by_id = {signal.get("id"): signal for signal in signals}
    negative_by_target: Counter[str] = Counter()
    for event in feedback_events:
        if event.get("action") not in {"mark_irrelevant", "delete", "mute_source", "dismiss"}:
            continue
        signal = signal_by_id.get(event.get("signal_id"), {})
        target = signal.get("source_id") or event.get("signal_id")
        if target:
            negative_by_target[target] += 1
    return [
        {"target_ref": target, "negative_count": count, "reason": "repeated negative feedback"}
        for target, count in sorted(negative_by_target.items())
        if count >= 2
    ]


def _component_score(interactions: list[dict[str, Any]], key: str) -> float:
    values = [float(item.get(f"{key}_score", 0.0)) for item in interactions if item.get(f"{key}_score") is not None]
    if not values:
        return 0.0
    return max(0.0, min(1.0, sum(values) / len(values)))


def _latest_time(values: list[Any]) -> datetime | None:
    parsed = [_parse_time(value) for value in values if value]
    return max(parsed) if parsed else None


def _parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require(obj: dict[str, Any], keys: list[str]) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise SocialEnvironmentError(f"missing required keys: {', '.join(missing)}")
