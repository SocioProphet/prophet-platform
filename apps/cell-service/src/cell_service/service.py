from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .clickhouse_facts import CellFactSink, InMemoryCellFactSink
from .extraction import ExtractionError, extract_with_patterns
from .feed import private_feed_document, rss_feed_document
from .lampstand_adapter import LampstandAdapterError, LampstandIngestAdapter
from .policy import PolicyEngine, PolicyError, StaticPolicyEngine, require_allowed
from .publication import cell_publication_bundle
from .repository import CellRepository, InMemoryCellRepository, RepositoryError


class ServiceError(ValueError):
    """Raised when a request violates the cell service contract."""


@dataclass(frozen=True)
class ResourceRef:
    collection: str
    identifier: str


class CellService:
    """Minimal Personal Intelligence Cell service.

    The service is repository-backed, policy-gated, deterministic-extraction
    capable, publication-aware, Lampstand-source-aware, and emits analytical
    facts for the ClickHouse lane.
    """

    def __init__(
        self,
        repository: CellRepository | None = None,
        policy_engine: PolicyEngine | None = None,
        fact_sink: CellFactSink | None = None,
    ) -> None:
        self._repo = repository or InMemoryCellRepository()
        self._policy = policy_engine or StaticPolicyEngine()
        self._facts = fact_sink or InMemoryCellFactSink()
        self._lampstand = LampstandIngestAdapter()

    def health(self) -> dict[str, str]:
        return {
            "service": "cell-service",
            "status": "ok",
            "time": _now(),
            "storage": self._repo.__class__.__name__,
            "policy": self._policy.__class__.__name__,
            "extraction": "deterministic-template-v1",
            "feed": "private-json+rss-v1",
            "publication": "slash-topics+new-hope+sherlock-v1",
            "source_adapter": "lampstand-v1",
            "facts": self._facts.__class__.__name__,
        }

    def create_cell(self, cell: dict[str, Any]) -> dict[str, Any]:
        self._require(cell, ["id", "owner_ref", "kind", "policy_ref", "memory_ref"])
        if cell["kind"] not in {"personal", "project", "community", "organization", "mission"}:
            raise ServiceError(f"unsupported cell kind: {cell['kind']}")
        self._require_allowed("cell.create", cell, cell.get("policy_ref"))
        prepared = self._with_timestamps(cell)
        prepared.setdefault("state", "active")
        return self._create("cells", prepared, "Cell")

    def get_cell(self, cell_id: str) -> dict[str, Any]:
        return self._get("cells", cell_id, "Cell")

    def list_cells(self) -> list[dict[str, Any]]:
        return self._list("cells")

    def put_cell_config(self, config: dict[str, Any]) -> dict[str, Any]:
        self._require(
            config,
            ["cell_id", "data_location_policy", "sync_policy", "backup_policy", "resource_budget_defaults", "local_first_mode"],
        )
        cell = self.get_cell(config["cell_id"])
        if not isinstance(config["local_first_mode"], bool):
            raise ServiceError("CellConfig.local_first_mode must be boolean")
        self._require_allowed("cell.configure", config, cell.get("policy_ref"))
        prepared = deepcopy(config)
        prepared.setdefault("id", f"cell-config:{config['cell_id']}")
        return self._put("cell_configs", config["cell_id"], prepared)

    def get_cell_config(self, cell_id: str) -> dict[str, Any]:
        return self._get("cell_configs", cell_id, "CellConfig")

    def create_source(self, source: dict[str, Any]) -> dict[str, Any]:
        self._require(source, ["id", "kind", "uri", "trust_profile", "crawl_profile", "provenance_profile", "policy_ref"])
        if source["kind"] in {"blockchain", "payment_rail", "marketplace", "governance_vote"} and source.get("enabled"):
            raise ServiceError("ledger/payment/governance source adapters must be disabled by default")
        self._require_allowed("source.create", source, source.get("policy_ref"))
        prepared = deepcopy(source)
        prepared.setdefault("enabled", True)
        return self._create("sources", prepared, "Source")

    def get_source(self, source_id: str) -> dict[str, Any]:
        return self._get("sources", source_id, "Source")

    def list_sources(self) -> list[dict[str, Any]]:
        return self._list("sources")

    def create_watch(self, watch: dict[str, Any]) -> dict[str, Any]:
        self._require(
            watch,
            ["id", "cell_id", "pattern_refs", "source_scope", "relevance_policy", "notification_policy", "resource_budget", "state"],
        )
        cell = self.get_cell(watch["cell_id"])
        if not isinstance(watch["pattern_refs"], list):
            raise ServiceError("Watch.pattern_refs must be a list")
        if not isinstance(watch["source_scope"], list):
            raise ServiceError("Watch.source_scope must be a list")
        for source_id in watch["source_scope"]:
            self.get_source(source_id)
        self._require_allowed("watch.create", watch, watch.get("relevance_policy") or cell.get("policy_ref"))
        prepared = self._with_timestamps(watch)
        return self._create("watches", prepared, "Watch")

    def get_watch(self, watch_id: str) -> dict[str, Any]:
        return self._get("watches", watch_id, "Watch")

    def list_watches(self, cell_id: str | None = None) -> list[dict[str, Any]]:
        watches = self._list("watches")
        if cell_id is None:
            return watches
        return [watch for watch in watches if watch.get("cell_id") == cell_id]

    def create_watch_pattern(self, pattern: dict[str, Any]) -> dict[str, Any]:
        self._require(pattern, ["id", "watch_id", "pattern_kind", "raw_expression", "version"])
        watch = self.get_watch(pattern["watch_id"])
        self.validate_watch_pattern(pattern)
        self._require_allowed("watch_pattern.create", pattern, watch.get("relevance_policy"))
        prepared = deepcopy(pattern)
        stored = self._create("watch_patterns", prepared, "WatchPattern")
        if stored["id"] not in watch["pattern_refs"]:
            watch["pattern_refs"].append(stored["id"])
            self._put("watches", watch["id"], watch)
        return stored

    def get_watch_pattern(self, pattern_id: str) -> dict[str, Any]:
        return self._get("watch_patterns", pattern_id, "WatchPattern")

    def list_watch_patterns(self, watch_id: str | None = None) -> list[dict[str, Any]]:
        patterns = self._list("watch_patterns")
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

    def extract_for_watch(self, watch_id: str, text: str) -> dict[str, Any]:
        watch = self.get_watch(watch_id)
        patterns = self.list_watch_patterns(watch_id)
        if not patterns:
            pattern_refs = watch.get("pattern_refs", [])
            patterns = [self.get_watch_pattern(pattern_ref) for pattern_ref in pattern_refs if self._exists("watch_patterns", pattern_ref)]
        if not patterns:
            raise ServiceError(f"Watch has no deterministic patterns: {watch_id}")
        try:
            result = extract_with_patterns(patterns, text)
        except ExtractionError as exc:
            raise ServiceError(str(exc)) from exc
        return {
            "pattern_id": result.pattern_id,
            "pattern_kind": result.pattern_kind,
            "matched": result.matched,
            "extractions": result.extractions,
            "confidence_score": result.confidence_score,
        }

    def ingest_lampstand_result(
        self,
        result: dict[str, Any],
        *,
        cell_id: str,
        watch_id: str,
        text: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        try:
            source = self._lampstand.source_from_result(result)
            if not self._exists("sources", source["id"]):
                self.create_source(source)
            signal_input = self._lampstand.signal_input_from_result(
                result,
                cell_id=cell_id,
                watch_id=watch_id,
                text=text,
                title=title,
            )
        except LampstandAdapterError as exc:
            raise ServiceError(str(exc)) from exc
        return self.ingest_text_signal(**signal_input)

    def ingest_text_signal(
        self,
        *,
        signal_id: str,
        cell_id: str,
        source_id: str,
        watch_id: str,
        text: str,
        title: str | None = None,
        evidence_refs: list[str] | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        extraction = self.extract_for_watch(watch_id, text)
        if not extraction["matched"]:
            raise ServiceError(f"text did not match deterministic watch patterns for {watch_id}")
        evidence = evidence_refs or [f"evidence://cell-service/text/{signal_id}"]
        signal = {
            "id": signal_id,
            "cell_id": cell_id,
            "source_id": source_id,
            "watch_id": watch_id,
            "observed_at": observed_at or _now(),
            "title": title or text[:120],
            "summary": text,
            "entities": [],
            "claims": [],
            "extractions": extraction["extractions"],
            "pattern_id": extraction["pattern_id"],
            "pattern_kind": extraction["pattern_kind"],
            "evidence_refs": evidence,
            "confidence_score": extraction["confidence_score"],
            "policy_status": "allowed",
        }
        return self.ingest_signal(signal)

    def ingest_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        self._require(signal, ["id", "cell_id", "source_id", "watch_id", "observed_at", "evidence_refs", "policy_status"])
        self.get_cell(signal["cell_id"])
        source = self.get_source(signal["source_id"])
        self.get_watch(signal["watch_id"])
        if not signal.get("evidence_refs"):
            raise ServiceError("Signal.evidence_refs must be non-empty")
        self._require_allowed("signal.ingest", signal, source.get("policy_ref"))
        prepared = deepcopy(signal)
        scored = self.score_signal(prepared)
        stored = self._create("signals", scored, "Signal")
        self._facts.emit_signal_score(stored)
        self._facts.emit_watch_pattern_metric(stored)
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

    def get_signal(self, signal_id: str) -> dict[str, Any]:
        return self._get("signals", signal_id, "Signal")

    def emit_feed_item(self, feed_item: dict[str, Any]) -> dict[str, Any]:
        self._require(feed_item, ["id", "cell_id", "signal_id", "feed_kind", "created_at"])
        self.get_cell(feed_item["cell_id"])
        self._get("signals", feed_item["signal_id"], "Signal")
        decision = self._require_allowed("feed_item.emit", feed_item, feed_item.get("target_ref") or feed_item.get("policy_ref"))
        prepared = deepcopy(feed_item)
        prepared["policy_decision"] = decision
        self._require_policy_decision(prepared["policy_decision"])
        stored = self._create("feed_items", prepared, "FeedItem")
        self._facts.emit_notification_metric(stored)
        return stored

    def get_feed_item(self, feed_item_id: str) -> dict[str, Any]:
        return self._get("feed_items", feed_item_id, "FeedItem")

    def list_feed_items(self, cell_id: str | None = None) -> list[dict[str, Any]]:
        items = self._list("feed_items")
        if cell_id is None:
            return items
        return [item for item in items if item.get("cell_id") == cell_id]

    def export_private_feed(self, cell_id: str) -> dict[str, Any]:
        cell = self.get_cell(cell_id)
        items = self.list_feed_items(cell_id)
        signals = {item["signal_id"]: self.get_signal(item["signal_id"]) for item in items}
        return private_feed_document(cell, items, signals)

    def export_rss_feed(self, cell_id: str) -> str:
        cell = self.get_cell(cell_id)
        items = self.list_feed_items(cell_id)
        signals = {item["signal_id"]: self.get_signal(item["signal_id"]) for item in items}
        return rss_feed_document(cell=cell, feed_items=items, signals=signals)

    def publication_bundle_for_feed_item(self, feed_item_id: str) -> dict[str, Any]:
        feed_item = self.get_feed_item(feed_item_id)
        signal = self.get_signal(feed_item["signal_id"])
        watch = self.get_watch(signal["watch_id"])
        cell = self.get_cell(feed_item["cell_id"])
        return cell_publication_bundle(cell=cell, watch=watch, signal=signal, feed_item=feed_item)

    def append_intent_event(self, intent_event: dict[str, Any]) -> dict[str, Any]:
        self._require(intent_event, ["id", "cell_id", "actor_ref", "intent_text", "structured_intent", "created_at"])
        self.get_cell(intent_event["cell_id"])
        if not intent_event["intent_text"]:
            raise ServiceError("IntentEvent.intent_text must be non-empty")
        if not isinstance(intent_event["structured_intent"], dict):
            raise ServiceError("IntentEvent.structured_intent must be object")
        decision = self._require_allowed("intent_event.append", intent_event, intent_event.get("policy_ref"))
        prepared = deepcopy(intent_event)
        prepared["policy_decision"] = decision
        self._require_policy_decision(prepared["policy_decision"])
        return self._create("intent_events", prepared, "IntentEvent")

    def record_feedback_event(self, feedback_event: dict[str, Any]) -> dict[str, Any]:
        self._require(feedback_event, ["id", "cell_id", "signal_id", "actor_ref", "action", "created_at"])
        self.get_cell(feedback_event["cell_id"])
        signal = self._get("signals", feedback_event["signal_id"], "Signal")
        if feedback_event["action"] not in {"follow", "mark_relevant", "mark_irrelevant", "delete", "mute_source", "promote_source", "refine_watch", "share", "save", "dismiss"}:
            raise ServiceError(f"unsupported FeedbackEvent.action: {feedback_event['action']}")
        self._require_allowed("feedback_event.record", feedback_event, None)
        stored = self._create("feedback_events", feedback_event, "FeedbackEvent")
        self._facts.emit_feedback_outcome(stored, signal)
        return stored

    def export_cell_archive(self, archive: dict[str, Any]) -> dict[str, Any]:
        self._require(archive, ["id", "cell_id", "schema_version", "manifest", "created_at"])
        cell = self.get_cell(archive["cell_id"])
        if not isinstance(archive["manifest"], dict):
            raise ServiceError("CellArchive.manifest must be object")
        if not archive.get("restore_dry_run_report_ref"):
            raise ServiceError("CellArchive.restore_dry_run_report_ref is required for first runtime lane")
        self._require_allowed("cell_archive.export", archive, archive.get("redaction_policy_ref") or cell.get("policy_ref"))
        return self._create("cell_archives", archive, "CellArchive")

    def analytics_snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return self._facts.snapshot()

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
            "private_feed": self.export_private_feed(cell["id"]),
            "rss_feed": self.export_rss_feed(cell["id"]),
            "publication_bundle": self.publication_bundle_for_feed_item(feed["id"]),
            "analytics": self.analytics_snapshot(),
        }

    def _source_trust(self, source_id: str) -> float:
        source = self.get_source(source_id)
        trust_profile = source.get("trust_profile", {})
        score = trust_profile.get("default_trust_score", 0.5)
        self._validate_score("source.trust_profile.default_trust_score", score)
        return float(score)

    def _require_allowed(self, operation: str, resource: dict[str, Any], policy_ref: str | None) -> dict[str, Any]:
        try:
            return require_allowed(self._policy.decide(operation, resource, policy_ref), operation)
        except PolicyError as exc:
            raise ServiceError(str(exc)) from exc

    def _create(self, collection: str, obj: dict[str, Any], label: str) -> dict[str, Any]:
        try:
            return self._repo.create(collection, obj)
        except RepositoryError as exc:
            raise ServiceError(f"{label} persistence error: {exc}") from exc

    def _put(self, collection: str, key: str, obj: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._repo.put(collection, key, obj)
        except RepositoryError as exc:
            raise ServiceError(f"persistence error: {exc}") from exc

    def _get(self, collection: str, key: str, label: str) -> dict[str, Any]:
        try:
            return self._repo.get(collection, key)
        except RepositoryError as exc:
            raise ServiceError(f"{label} not found: {key}") from exc

    def _exists(self, collection: str, key: str) -> bool:
        try:
            return self._repo.exists(collection, key)
        except RepositoryError as exc:
            raise ServiceError(f"persistence error: {exc}") from exc

    def _list(self, collection: str) -> list[dict[str, Any]]:
        try:
            return self._repo.list(collection)
        except RepositoryError as exc:
            raise ServiceError(f"persistence error: {exc}") from exc

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
