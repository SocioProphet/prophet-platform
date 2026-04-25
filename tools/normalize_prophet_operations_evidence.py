#!/usr/bin/env python3
"""Normalize raw local operations observations into Prophet operations evidence.

This helper is intentionally vendor-neutral. It accepts a compact raw JSON input and emits
Prophet-native operational signals, optional topology evidence, health assessments, and
optimization recommendations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

POLICY_FABRIC_OPERATIONS_DECISION_CONTRACT = "schema://policy-fabric/contracts/prophet_operations_action_decision_v1.schema.json"
DEFAULT_OPERATIONS_POLICY_REF = "policy://operations/default-action-gates/v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}-{_sha256_bytes(encoded)[:16]}"


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_signal(raw_signal: Dict[str, Any], *, source: Dict[str, Any], observed_at: str, raw_ref: str | None, raw_sha256: str | None) -> Dict[str, Any]:
    subject = raw_signal.get("subject") or raw_signal.get("resource") or {}
    signal = raw_signal.get("signal") or raw_signal.get("metric") or raw_signal.get("event") or {}
    normalized = {
        "kind": "ProphetOperationalSignal",
        "schema_version": "v0.1",
        "signal_id": raw_signal.get("signal_id") or _stable_id("opsig", raw_signal),
        "source": {
            "system": source.get("system", "unknown"),
            "emitter": source.get("emitter", "normalize_prophet_operations_evidence"),
            "ref": source.get("ref"),
        },
        "observed_at": raw_signal.get("observed_at") or observed_at,
        "subject": {
            "id": str(subject.get("id") or subject.get("name") or "unknown"),
            "type": str(subject.get("type") or "unknown"),
            "name": subject.get("name"),
            "namespace": subject.get("namespace"),
            "owner_ref": subject.get("owner_ref"),
        },
        "signal": {
            "name": str(signal.get("name") or raw_signal.get("name") or "unknown"),
            "type": signal.get("type") or raw_signal.get("type") or "metric",
            "value": signal.get("value", raw_signal.get("value")),
            "unit": signal.get("unit", raw_signal.get("unit")),
            "severity": signal.get("severity", raw_signal.get("severity", "unknown")),
        },
        "evidence_refs": _as_list(raw_signal.get("evidence_refs")),
        "raw_ref": raw_ref,
        "raw_sha256": raw_sha256,
        "notes": raw_signal.get("notes"),
    }
    return normalized


def normalize_topology(raw_topology: Dict[str, Any], *, observed_at: str, raw_ref: str | None, raw_sha256: str | None) -> Dict[str, Any]:
    normalized = {
        "kind": "ProphetRuntimeTopologyEvidence",
        "schema_version": "v0.1",
        "topology_id": raw_topology.get("topology_id") or _stable_id("topology", raw_topology),
        "observed_at": raw_topology.get("observed_at") or observed_at,
        "scope": raw_topology.get("scope", {}),
        "nodes": raw_topology.get("nodes", []),
        "edges": raw_topology.get("edges", []),
        "evidence_refs": _as_list(raw_topology.get("evidence_refs")),
        "raw_ref": raw_ref,
        "raw_sha256": raw_sha256,
    }
    return normalized


def assess_health(signal_records: Iterable[Dict[str, Any]], *, topology_ref: str | None = None) -> List[Dict[str, Any]]:
    assessments: Dict[str, Dict[str, Any]] = {}
    for record in signal_records:
        subject = record["subject"]
        key = f"{subject['type']}:{subject['id']}"
        severity = record.get("signal", {}).get("severity", "unknown")
        state = "healthy"
        reasons: List[str] = []
        if severity in {"critical", "error"}:
            state = "unhealthy"
            reasons.append(f"{record['signal']['name']} severity={severity}")
        elif severity == "warn":
            state = "degraded"
            reasons.append(f"{record['signal']['name']} severity=warn")
        current = assessments.get(key)
        if not current:
            current = {
                "kind": "ProphetServiceHealthAssessment",
                "schema_version": "v0.1",
                "assessment_id": _stable_id("health", {"subject": subject, "topology_ref": topology_ref}),
                "assessed_at": _utc_now(),
                "subject": subject,
                "health": {"state": "healthy", "score": 1.0, "summary": "No degraded signals observed.", "reasons": []},
                "input_signal_refs": [],
                "topology_ref": topology_ref,
                "policy_ref": None,
                "evidence_refs": [],
            }
            assessments[key] = current
        current["input_signal_refs"].append(record["signal_id"])
        if state == "unhealthy" or (state == "degraded" and current["health"]["state"] == "healthy"):
            current["health"]["state"] = state
            current["health"]["score"] = 0.2 if state == "unhealthy" else 0.6
            current["health"]["summary"] = f"{subject.get('name') or subject['id']} is {state}."
        current["health"]["reasons"].extend(reasons)
    return list(assessments.values())


def policy_decision_ref_for(recommendation_id: str) -> str:
    return f"policy-fabric://prophet-operations-action-decision/v1/{recommendation_id}"


def recommend(assessments: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recommendations: List[Dict[str, Any]] = []
    for assessment in assessments:
        state = assessment["health"]["state"]
        if state == "healthy":
            continue
        action_type = "investigate" if state == "degraded" else "isolate"
        subject = assessment["subject"]
        recommendation_id = _stable_id("oprec", {"assessment": assessment["assessment_id"], "action": action_type})
        rec = {
            "kind": "ProphetOptimizationRecommendation",
            "schema_version": "v0.1",
            "recommendation_id": recommendation_id,
            "created_at": _utc_now(),
            "subject": subject,
            "action": {
                "type": action_type,
                "intent": "restore_service_health",
                "description": f"{action_type} {subject.get('name') or subject['id']} based on health assessment.",
                "parameters": {},
            },
            "basis": {
                "health_assessment_ref": assessment["assessment_id"],
                "topology_ref": assessment.get("topology_ref"),
                "signal_refs": assessment.get("input_signal_refs", []),
                "reason": assessment["health"].get("summary"),
            },
            "policy_gate": {
                "required": True,
                "policy_ref": assessment.get("policy_ref") or DEFAULT_OPERATIONS_POLICY_REF,
                "decision_contract_ref": POLICY_FABRIC_OPERATIONS_DECISION_CONTRACT,
                "decision_ref": policy_decision_ref_for(recommendation_id),
                "decision": "pending",
            },
            "risk": {"level": "medium" if state == "degraded" else "high", "notes": None},
            "evidence_refs": assessment.get("evidence_refs", []),
        }
        recommendations.append(rec)
    return recommendations


def evidence_links_for(bundle_id: str, recommendations: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    for recommendation in recommendations:
        links.append(
            {
                "kind": "ProphetOperationsEvidenceLink",
                "schema_version": "v0.1",
                "link_id": _stable_id("opslink", {"bundle_id": bundle_id, "recommendation": recommendation["recommendation_id"]}),
                "from_ref": f"artifact://prophet-platform/operations/{bundle_id}",
                "to_ref": recommendation["policy_gate"]["decision_ref"],
                "relationship": "requires_policy_decision",
                "contract_ref": recommendation["policy_gate"]["decision_contract_ref"],
                "recommendation_ref": recommendation["recommendation_id"],
            }
        )
    return links


def normalize_document(raw: Dict[str, Any], *, raw_ref: str | None, raw_sha256: str | None) -> Dict[str, Any]:
    observed_at = raw.get("observed_at") or _utc_now()
    source = raw.get("source") or {"system": "local", "emitter": "normalize_prophet_operations_evidence"}
    signals = [normalize_signal(item, source=source, observed_at=observed_at, raw_ref=raw_ref, raw_sha256=raw_sha256) for item in raw.get("signals", [])]
    topology = normalize_topology(raw["topology"], observed_at=observed_at, raw_ref=raw_ref, raw_sha256=raw_sha256) if raw.get("topology") else None
    topology_ref = topology["topology_id"] if topology else None
    assessments = assess_health(signals, topology_ref=topology_ref)
    recommendations = recommend(assessments)
    bundle_id = raw.get("bundle_id") or _stable_id("opsbundle", raw)
    return {
        "kind": "ProphetOperationsEvidenceBundle",
        "schema_version": "v0.1",
        "bundle_id": bundle_id,
        "created_at": _utc_now(),
        "signals": signals,
        "topology": topology,
        "health_assessments": assessments,
        "recommendations": recommendations,
        "evidence_links": evidence_links_for(bundle_id, recommendations),
        "raw_ref": raw_ref,
        "raw_sha256": raw_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Raw operations observation JSON")
    parser.add_argument("--output", type=Path, required=True, help="Output normalized evidence bundle JSON")
    parser.add_argument("--raw-ref", default=None, help="Optional raw evidence reference URI/path")
    args = parser.parse_args()

    payload = args.input.read_bytes()
    raw = json.loads(payload.decode("utf-8"))
    bundle = normalize_document(raw, raw_ref=args.raw_ref or str(args.input), raw_sha256=_sha256_bytes(payload))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
