from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


class ServiceError(ValueError):
    """Raised when a request violates the cell service contract."""


@dataclass(frozen=True)
class ResourceRef:
    collection: str
    identifier: str


class CellService:
    """Minimal in-memory Personal Intelligence Cell service.

    This is intentionally not a crawler, database adapter, or UI service. It is the
    first governed runtime skeleton for the contract loop defined under
    contracts/cell/personal-intelligence-cell.loop.v1.example.json.
    """

    def __init__(self) -> None:
        self._cells: dict[str, dict[str, Any]] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._sources: dict[str, dict[str, Any]] = {}
        self._watches: dict[str, dict[str, Any]] = {}
        self._patterns: dict[str, dict[str, Any]] = {}
        self._signals: dict[str, dict[str, Any]] = {}
        self._feed_items: dict[str, dict[str, Any]] = {}
        self._intent_events: dict[str, dict[str, Any]] = {}
        self._feedback_events: dict[str, dict[str, Any]] = {}
        self._archives: dict[str, dict[str, Any]] = {}

    def health(self) -> dict[str, str]:
        return {
            "service": "cell-service",
            "status": "ok",
            "time": _now(),
        }

    def create_cell(self, cell: dict[str, Any]) -> dict[str, Any]:
        self._require(cell, ["id", "owner_ref", "kind", "policy_ref", "memory_ref"])
        if cell["kind"] not in {"personal", "project", "community", "organization", "mission"}:
            raise ServiceError(f"unsupported cell kind: {cell['kind']}")
        prepared = self._with_timestamps(cell)
        prepared.setdefault("state", "active")
        return self._put_unique(self._cells, prepared, "Cell")

    def get_cell(self, cell_id: str) -> dict[str, Any]:
        return self._get(self._cells, cell_id, "Cell")

    def list_cells(self) -> list[dict[str, Any]]:
        return self._list(self._cells)

    def put_cell_config(self, config: dict[str, Any]) -> dict[str, Any]:
        self._require(
            config,
            ["cell_id", "data_location_policy", "sync_policy", "backup_policy", "resource_budget_defaults", "local_first_mode"],
        )
        self.get_cell(config["cell_id"])
        if not isinstance(config["local_first_mode"], bool):
            raise ServiceError("CellConfig.local_first_mode must be boolean")
        prepared = deepcopy(config)
        prepared.setdefault("id", f"cell-config:{config['cell_id']}")
        self._configs[config["cell_id"]] = prepared
        return deepcopy(prepared)

    def get_cell_config(self, cell_id: str) -> dict[str, Any]:
        return self._get(self._configs, cell_id, "CellConfig")

    def create_source(self, source: dict[str, Any]) -> dict[str, Any]:
        self._require(source, ["id", "kind", "uri", "trust_profile", "crawl_profile", "provenance_profile", "policy_ref"])
        if source["kind"] in {"blockchain", "payment_rail", "marketplace", "governance_vote"} and source.get("enabled"):
            raise ServiceError("ledger/payment/governance source adapters must be disabled by default")
        prepared = deepcopy(source)
        prepared.setdefault("enabled", True)
        return self._put_unique(self._sources, prepared, "Source")

    def get_source(self, source_id: str) -> dict[str, Any]:
        return self._get(self._sources, source_id, "Source")

    def list_sources(self) -> list[dict[str, Any]]:
        return self._list(self._sources)

    def create_watch(self, watch: dict[str, Any]) -> dict[str, Any]:
        self._require(
            watch,
            ["id", "cell_id", "pattern_refs", "source_scope", "relevance_policy", "notification_policy", "resource_budget", "state"],
        )
        self.get_cell(watch["cell_id"])
        if not isinstance(watch["pattern_refs"], list):
            raise ServiceError("Watch.pattern_refs must be a list")
        if not isinstance(watch["source_scope"], list):
            raise ServiceError("Watch.source_scope must be a list")
        for source_id in watch["source_scope"]:
            self.get_source(source_id)
        prepared = self._with_timestamps(watch)
        return self._put_unique(self._watches, prepared, "Watch")

    def get_watch(self, watch_id: str) -> dict[str, Any]:
        return self._get(self._watches, watch_id, "Watch")

    def list_watches(self, cell_id: str | None = None) -> list[dict[str, Any]]:
        watches = self._list(self._watches)
        if cell_id is None:
            return watches
        return [watch for watch in watches if watch.get("cell_id") == cell_id]

    def create_watch_pattern(self, pattern: dict[str, Any]) -> dict[str, Any]:
        self._require(pattern, ["id", "watch_id", "pattern_kind", "raw_expression", "version"])
        watch = self.get_watch(pattern["watch_id"])
        self.validate_watch_pattern(pattern)
        prepared = deepcopy(pattern)
        stored = self._put_unique(self._patterns, prepared, "WatchPattern")
        if stored["id"] not in watch["pattern_refs"]:
            watch["pattern_refs"].append(stored["id"])
            self._watches[watch["id"]] = watch
        return stored

    def get_watch_pattern(self, pattern_id: str) -> dict[str, Any]:
        return self._get(self._patterns, pattern_id, "WatchPattern")

    def list_watch_patterns(self, watch_id: str | None = None) -> list[dict[str, Any]]:
        patterns = self._list(self._patterns)
        if watch_id is None:
            return patterns
        return [pattern for pattern in patterns if pattern.get("watch_id") == watch_id]

    def validate_watch_pattern(self, pattern: dict[str, Any]) -> dict[str, Any]:
        kind = pattern.get("pattern_kind")
        if kind not in {"phrase", "boolean", "regex", "semantic", "typed_template", "claim_template", "graph_pattern", "policy_trigger"}:
            raise ServiceError(f"unsupported WatchPattern.pattern_kind: {kind}")
        variables = pattern.get("variables", [])
        if variables is None:
            variables = []
        if not isinstance(variables, list):
            raise ServiceError("WatchPattern.variables must be a list")
        names: set[str] = set()
        for variable in variables:
            if not isinstance(variable, dict):
                raise ServiceError("WatchPattern variable must be an object")
            self._require(variable, ["name", "type", "required"])
            name = variable["name"]
            if not isinstance(name, str) or not name.replace("_", "a").isalnum() or name[0].isdigit():
                raise ServiceError(f"invalid WatchPattern variable name: {name!r}")
            if variable["type"] not in {"word", "text", "time", "date", "number", "money", "entity", "url", "email", "location", "custom"}:
                raise ServiceError(f"unsupported WatchPattern variable type: {variable['type']}")
            if not isinstance(variable["required"], bool):
                raise ServiceError(f"WatchPattern variable {name} required must be boolean")
            names.add(name)
        raw = pattern.get("raw_expression", "")
        for name in names:
            if f"${name}" not in raw:
                raise ServiceError(f"WatchPattern variable ${name} not referenced in raw_expression")
        for frame in pattern.get("frames", []) or []:
            if not isinstance(frame, dict):
                raise ServiceError("WatchPattern frame must be an object")
            for ref in frame.get("variable_refs", []) or []:
                if ref not in names:
                    raise ServiceError(f"WatchPattern frame references unknown variable: {ref}")
        return {"valid": True, "variables": sorted(names), "pattern_kind": kind}

    def ingest_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        self._require(signal, ["id", "cell_id", "source_id", "watch_id", "observed_at", "evidence_refs", "policy_status"])
        self.get_cell(signal["cell_id"])
        self.get_source(signal["source_id"])
        self.get_watch(signal["watch_id"])
        if not signal.get("evidence_refs"):
            raise ServiceError("Signal.evidence_refs must be non-empty")
        prepared = deepcopy(signal)
        scored = self.score_signal(prepared)
        stored = self._put_unique(self._signals, scored, "Signal")
        return stored

    def score_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        prepared = deepcopy(signal)
        extraction_count = len(prepared.get("extractions", {}) or {})
        evidence_count = len(prepared.get("evidence_refs", []) or [])
        prepared.setdefault("novelty_score", 0.75)
        prepared.setdefault("relevance_score", min(1.0, 0.55 + 0.1 * extraction_count + 0.05 * evidence_count))
        prepared.setdefault("confidence_score", min(1.0, 0.6 + 0.1 * evidence_count))
        prepared.setdefault("source_trust_score", self._source_trust(prepared["source_id"]))
        for key in ["novelty_score", "relevance_score", "confidence_score", "source_trust_score"]:
            self._validate_score(key, prepared[key])
        prepared.setdefault("reputation_effects", [])
        return prepared

    def emit_feed_item(self, feed_item: dict[str, Any]) -> dict[str, Any]:
        self._require(feed_item, ["id", "cell_id", "signal_id", "feed_kind", "policy_decision", "created_at"])
        self.get_cell(feed_item["cell_id"])
        self._get(self._signals, feed_item["signal_id"], "Signal")
        self._require_policy_decision(feed_item["policy_decision"])
        return self._put_unique(self._feed_items, feed_item, "FeedItem")

    def append_intent_event(self, intent_event: dict[str, Any]) -> dict[str, Any]:
        self._require(intent_event, ["id", "cell_id", "actor_ref", "intent_text", "structured_intent", "policy_decision", "created_at"])
        self.get_cell(intent_event["cell_id"])
        if not intent_event["intent_text"]:
            raise ServiceError("IntentEvent.intent_text must be non-empty")
        if not isinstance(intent_event["structured_intent"], dict):
            raise ServiceError("IntentEvent.structured_intent must be object")
        self._require_policy_decision(intent_event["policy_decision"])
        return self._put_unique(self._intent_events, intent_event, "IntentEvent")

    def record_feedback_event(self, feedback_event: dict[str, Any]) -> dict[str, Any]:
        self._require(feedback_event, ["id", "cell_id", "signal_id", "actor_ref", "action", "created_at"])
        self.get_cell(feedback_event["cell_id"])
        self._get(self._signals, feedback_event["signal_id"], "Signal")
        if feedback_event["action"] not in {"follow", "mark_relevant", "mark_irrelevant", "delete", "mute_source", "promote_source", "refine_watch", "share", "save", "dismiss"}:
            raise ServiceError(f"unsupported FeedbackEvent.action: {feedback_event['action']}")
        return self._put_unique(self._feedback_events, feedback_event, "FeedbackEvent")

    def export_cell_archive(self, archive: dict[str, Any]) -> dict[str, Any]:
        self._require(archive, ["id", "cell_id", "schema_version", "manifest", "created_at"])
        self.get_cell(archive["cell_id"])
        if not isinstance(archive["manifest"], dict):
            raise ServiceError("CellArchive.manifest must be object")
        if not archive.get("restore_dry_run_report_ref"):
            raise ServiceError("CellArchive.restore_dry_run_report_ref is required for first runtime lane")
        return self._put_unique(self._archives, archive, "CellArchive")

    def run_loop_contract(self, loop: dict[str, Any]) -> dict[str, Any]:
        cell = self.create_cell(loop["cell"])
        config = self.put_cell_config(loop["cell_config"])
        source = self.create_source(loop["source"])
        watch = self.create_watch(loop["watch"])
        pattern = self.create_watch_pattern(loop["watch_pattern"])
        signal = self.ingest_signal(loop["signal"])
        feed = self.emit_feed_item(loop["feed_item"])
        intent = self.append_intent_event(loop["intent_event"])
        feedback = self.record_feedback_event(loop["feedback_event"])
        archive = self.export_cell_archive(loop["cell_archive"])
        return {
            "cell": cell,
            "cell_config": config,
            "source": source,
            "watch": watch,
            "watch_pattern": pattern,
            "signal": signal,
            "feed_item": feed,
            "intent_event": intent,
            "feedback_event": feedback,
            "cell_archive": archive,
        }

    def _source_trust(self, source_id: str) -> float:
        source = self.get_source(source_id)
        trust_profile = source.get("trust_profile", {})
        score = trust_profile.get("default_trust_score", 0.5)
        self._validate_score("source.trust_profile.default_trust_score", score)
        return float(score)

    def _put_unique(self, collection: dict[str, dict[str, Any]], obj: dict[str, Any], label: str) -> dict[str, Any]:
        obj_id = obj["id"]
        if obj_id in collection:
            raise ServiceError(f"{label} already exists: {obj_id}")
        collection[obj_id] = deepcopy(obj)
        return deepcopy(obj)

    def _get(self, collection: dict[str, dict[str, Any]], obj_id: str, label: str) -> dict[str, Any]:
        try:
            return deepcopy(collection[obj_id])
        except KeyError as exc:
            raise ServiceError(f"{label} not found: {obj_id}") from exc

    def _list(self, collection: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [deepcopy(value) for value in collection.values()]

    def _with_timestamps(self, obj: dict[str, Any]) -> dict[str, Any]:
        prepared = deepcopy(obj)
        stamp = _now()
        prepared.setdefault("created_at", stamp)
        prepared.setdefault("updated_at", stamp)
        return prepared

    def _require(self, obj: dict[str, Any], keys: Iterable[str]) -> None:
        missing = [key for key in keys if key not in obj]
        if missing:
            raise ServiceError(f"missing required keys: {', '.join(missing)}")

    def _require_policy_decision(self, decision: dict[str, Any]) -> None:
        if not isinstance(decision, dict):
            raise ServiceError("policy_decision must be object")
        self._require(decision, ["decision", "policy_ref", "decided_at"])
        if decision["decision"] not in {"allow", "deny", "quarantine", "review_required", "redact"}:
            raise ServiceError(f"unsupported policy decision: {decision['decision']}")

    def _validate_score(self, key: str, value: Any) -> None:
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ServiceError(f"{key} must be numeric 0..1")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
