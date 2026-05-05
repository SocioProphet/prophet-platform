from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class PublicationError(ValueError):
    """Raised when a cell artifact cannot be mapped to publication surfaces."""


def slash_topic_surface(
    *,
    cell: dict[str, Any],
    watch: dict[str, Any],
    signal: dict[str, Any],
    feed_item: dict[str, Any],
    topic_ref: str | None = None,
) -> dict[str, Any]:
    """Build a slash-topic scoped publication surface from a cell signal.

    Slash topics are governed, replayable scopes for search and knowledge
    surfaces. The cell runtime maps each feed item into a topic-scoped record
    with policy and evidence lineage preserved.
    """

    _require(cell, ["id", "owner_ref", "kind"])
    _require(watch, ["id", "cell_id"])
    _require(signal, ["id", "source_id", "watch_id", "evidence_refs"])
    _require(feed_item, ["id", "cell_id", "signal_id", "policy_decision"])
    if signal["watch_id"] != watch["id"]:
        raise PublicationError("signal.watch_id must match watch.id")
    if feed_item["signal_id"] != signal["id"]:
        raise PublicationError("feed_item.signal_id must match signal.id")

    policy = feed_item.get("policy_decision") or {}
    return {
        "surfaceKind": "slash-topic-cell-signal",
        "schemaVersion": "v0.1",
        "topicRef": topic_ref or _default_topic_ref(cell, watch),
        "cellRef": cell["id"],
        "watchRef": watch["id"],
        "signalRef": signal["id"],
        "feedItemRef": feed_item["id"],
        "title": feed_item.get("title") or signal.get("title") or signal["id"],
        "summary": feed_item.get("body") or signal.get("summary") or "",
        "extractions": signal.get("extractions", {}),
        "policyDecisionRefs": [policy.get("policy_ref")] if policy.get("policy_ref") else [],
        "policyDecision": policy.get("decision"),
        "evidenceRefs": signal.get("evidence_refs", []),
        "replay": {
            "sourceRef": signal.get("source_id"),
            "observedAt": signal.get("observed_at"),
            "createdAt": feed_item.get("created_at"),
        },
    }


def new_hope_membrane_event(
    *,
    cell: dict[str, Any],
    signal: dict[str, Any],
    feed_item: dict[str, Any],
    membrane_ref: str = "membrane://new-hope/cell-feed-publication",
) -> dict[str, Any]:
    """Build a New Hope-compatible membrane event for a feed publication."""

    _require(cell, ["id", "owner_ref", "kind"])
    _require(signal, ["id", "source_id", "watch_id", "evidence_refs"])
    _require(feed_item, ["id", "cell_id", "signal_id", "policy_decision"])
    policy = feed_item.get("policy_decision") or {}
    decision = policy.get("decision") or "review_required"
    membrane_outcome = {
        "allow": "admit",
        "deny": "reject",
        "quarantine": "quarantine",
        "review_required": "hold",
        "redact": "hold",
    }.get(decision, "hold")
    return {
        "schemaVersion": "new-hope-cell-membrane.v0.1",
        "carrierRef": f"carrier://cell/{signal['id']}",
        "receptorRef": f"receptor://cell/{cell['id']}/feed",
        "membraneRef": membrane_ref,
        "membraneOutcome": membrane_outcome,
        "policyDecision": policy,
        "message": {
            "messageRef": feed_item["id"],
            "threadRef": signal.get("watch_id"),
            "claimRefs": [claim.get("text") for claim in signal.get("claims", []) if isinstance(claim, dict) and claim.get("text")],
            "citationRefs": signal.get("evidence_refs", []),
            "entityRefs": [entity.get("text") for entity in signal.get("entities", []) if isinstance(entity, dict) and entity.get("text")],
            "title": feed_item.get("title") or signal.get("title") or signal["id"],
            "summary": feed_item.get("body") or signal.get("summary") or "",
        },
        "lineage": {
            "cellRef": cell["id"],
            "sourceRef": signal.get("source_id"),
            "signalRef": signal["id"],
            "feedItemRef": feed_item["id"],
            "evidenceRefs": signal.get("evidence_refs", []),
        },
        "emittedAt": _now(),
    }


def sherlock_search_packet(
    *,
    cell: dict[str, Any],
    watch: dict[str, Any],
    signal: dict[str, Any],
    feed_item: dict[str, Any],
    issued_by: str | None = None,
    workroom_ref: str | None = None,
    playbook_id: str = "playbook://personal-intelligence-cell/watch-signal",
    sensitivity_ceiling: str = "internal",
) -> dict[str, Any]:
    """Build a Sherlock-compatible search packet for a cell signal."""

    _require(cell, ["id", "owner_ref", "kind"])
    _require(watch, ["id", "cell_id"])
    _require(signal, ["id", "source_id", "watch_id", "evidence_refs"])
    _require(feed_item, ["id", "cell_id", "signal_id", "policy_decision"])
    policy = feed_item.get("policy_decision") or {}
    title = feed_item.get("title") or signal.get("title") or signal["id"]
    summary = feed_item.get("body") or signal.get("summary") or title
    evidence_refs = signal.get("evidence_refs", [])
    return {
        "schemaVersion": "v0.1",
        "searchPacketId": f"search-packet://cell/{signal['id']}",
        "workroomRef": workroom_ref or f"workroom://cell/{cell['id']}",
        "playbookId": playbook_id,
        "query": {
            "text": watch.get("title") or watch.get("description") or signal.get("summary") or title,
            "issuedBy": issued_by or cell.get("owner_ref") or "agent://cell-service",
            "issuedAt": _now(),
        },
        "scope": {
            "allowedSourceClasses": [signal.get("source_id", "source://unknown")],
            "sensitivityCeiling": sensitivity_ceiling,
            "policyDecisionRefs": [policy.get("policy_ref")] if policy.get("policy_ref") else [],
        },
        "results": [
            {
                "resultId": signal["id"],
                "sourceRef": signal.get("source_id", "source://unknown"),
                "title": title,
                "summary": summary,
                "confidence": float(signal.get("confidence_score", 0.5)),
                "freshness": _freshness(signal.get("observed_at")),
                "sensitivity": sensitivity_ceiling,
                "citationRefs": evidence_refs,
                "evidenceRef": evidence_refs[0] if evidence_refs else None,
            }
        ],
        "evidenceRefs": evidence_refs,
    }


def cell_publication_bundle(
    *,
    cell: dict[str, Any],
    watch: dict[str, Any],
    signal: dict[str, Any],
    feed_item: dict[str, Any],
) -> dict[str, Any]:
    """Build all first-class publication bridges for a cell feed item."""

    return {
        "slashTopicSurface": slash_topic_surface(cell=cell, watch=watch, signal=signal, feed_item=feed_item),
        "newHopeMembraneEvent": new_hope_membrane_event(cell=cell, signal=signal, feed_item=feed_item),
        "sherlockSearchPacket": sherlock_search_packet(cell=cell, watch=watch, signal=signal, feed_item=feed_item),
    }


def _default_topic_ref(cell: dict[str, Any], watch: dict[str, Any]) -> str:
    watch_slug = str(watch.get("title") or watch["id"]).lower()
    watch_slug = "".join(ch if ch.isalnum() else "-" for ch in watch_slug).strip("-")
    return f"/cell/{cell['kind']}/{watch_slug or 'watch'}"


def _freshness(observed_at: str | None) -> str:
    if not observed_at:
        return "unknown"
    # Keep deterministic and conservative for the first packet lane. Runtime can
    # replace this with wall-clock comparison later.
    return "current"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require(obj: dict[str, Any], keys: list[str]) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise PublicationError(f"missing required publication keys: {', '.join(missing)}")
