from __future__ import annotations

import re
from typing import Any


class LampstandAdapterError(ValueError):
    """Raised when a Lampstand ingest result cannot be adapted into cell state."""


class LampstandIngestAdapter:
    """Adapt Lampstand carrier-ingested results into Personal Intelligence Cell objects.

    The adapter consumes the result shape emitted by `apps/lampstand` ingest:
    carrier refs, payload/envelope/receipt refs, catalog entry, classifiers,
    zone refs, topic refs, and publication request metadata.
    """

    def __init__(self, *, default_policy_ref: str = "policy://cell/lampstand/default") -> None:
        self.default_policy_ref = default_policy_ref

    def source_from_result(self, result: dict[str, Any], *, policy_ref: str | None = None) -> dict[str, Any]:
        self._require_result(result)
        entry = result.get("entry", {})
        carrier_ref = result["carrier_ref"]
        source_id = f"source://lampstand/{_safe_ref(carrier_ref)}"
        return {
            "id": source_id,
            "kind": "local_fs",
            "uri": entry.get("payload_ref") or result.get("payload_path") or carrier_ref,
            "trust_profile": {
                "default_trust_score": 0.85,
                "basis": "lampstand_local_receipt",
            },
            "crawl_profile": {
                "mode": "receipt_catalog",
                "zone_ref": entry.get("zone_ref") or result.get("zone_ref"),
                "topic_ref": entry.get("topic_ref") or result.get("topic_ref"),
            },
            "provenance_profile": {
                "carrier_ref": carrier_ref,
                "receipt_ref": result.get("receipt_path") or entry.get("receipt_ref"),
                "payload_ref": entry.get("payload_ref") or result.get("payload_path"),
                "envelope_ref": entry.get("envelope_ref") or result.get("event_path"),
                "catalog_ref": result.get("catalog_path"),
            },
            "policy_ref": policy_ref or self.default_policy_ref,
            "enabled": True,
        }

    def signal_input_from_result(
        self,
        result: dict[str, Any],
        *,
        cell_id: str,
        watch_id: str,
        text: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        self._require_result(result)
        entry = result.get("entry", {})
        carrier_ref = result["carrier_ref"]
        correlation_id = entry.get("correlation_id") or _safe_ref(carrier_ref)
        source = self.source_from_result(result)
        evidence_refs = self.evidence_refs_from_result(result)
        adapted_text = text or self.text_from_result(result)
        return {
            "signal_id": f"signal://lampstand/{correlation_id}",
            "cell_id": cell_id,
            "source_id": source["id"],
            "watch_id": watch_id,
            "text": adapted_text,
            "title": title or f"Lampstand carrier ingested: {carrier_ref}",
            "evidence_refs": evidence_refs,
            "observed_at": entry.get("created_at") or result.get("created_at"),
        }

    def evidence_refs_from_result(self, result: dict[str, Any]) -> list[str]:
        self._require_result(result)
        entry = result.get("entry", {})
        refs = [
            entry.get("receipt_ref") or result.get("receipt_path"),
            entry.get("payload_ref") or result.get("payload_path"),
            entry.get("envelope_ref") or result.get("event_path"),
            result.get("catalog_path"),
            result.get("carrier_ref"),
        ]
        publication = result.get("publication_request") or {}
        refs.extend([publication.get("request_ref"), publication.get("publication_ref")])
        return [ref for ref in refs if isinstance(ref, str) and ref]

    def text_from_result(self, result: dict[str, Any]) -> str:
        self._require_result(result)
        entry = result.get("entry", {})
        classifiers = ", ".join(entry.get("classifiers", []) or [])
        bits = [
            f"Lampstand carrier {result['carrier_ref']} ingested",
            f"scope {entry.get('scope_ref', 'scope://unknown')}",
            f"zone {entry.get('zone_ref', 'zone://unknown')}",
        ]
        if entry.get("topic_ref"):
            bits.append(f"topic {entry['topic_ref']}")
        if classifiers:
            bits.append(f"classifiers {classifiers}")
        return "; ".join(bits) + "."

    def _require_result(self, result: dict[str, Any]) -> None:
        if not isinstance(result, dict):
            raise LampstandAdapterError("Lampstand result must be object")
        if result.get("ok") is not True:
            raise LampstandAdapterError("Lampstand result must have ok=true")
        if not result.get("carrier_ref"):
            raise LampstandAdapterError("Lampstand result missing carrier_ref")
        if not isinstance(result.get("entry"), dict):
            raise LampstandAdapterError("Lampstand result missing entry object")


def _safe_ref(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "unknown"
