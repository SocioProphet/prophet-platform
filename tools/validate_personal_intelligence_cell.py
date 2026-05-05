#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/cell/personal-intelligence-cell.schema.json"
FIXTURES_PATH = ROOT / "schemas/cell/watch-pattern-fixtures.json"
RUNTIME_DOC_PATH = ROOT / "docs/PERSONAL_INTELLIGENCE_CELL_RUNTIME.md"
LOOP_CONTRACT_PATH = ROOT / "contracts/cell/personal-intelligence-cell.loop.v1.example.json"
POSTGRES_MIGRATION_PATH = ROOT / "infra/datastores/postgres/migrations/cell/0001_personal_intelligence_cell.sql"
CLICKHOUSE_SCHEMA_PATH = ROOT / "infra/datastores/clickhouse/cell/0001_personal_intelligence_cell_analytics.sql"
POLICY_PATH = ROOT / "apps/cell-service/src/cell_service/policy.py"
SERVICE_PATH = ROOT / "apps/cell-service/src/cell_service/service.py"

EXPECTED_DEFS = {
    "Cell",
    "CellConfig",
    "Watch",
    "WatchPattern",
    "PatternVariable",
    "PatternFrame",
    "Source",
    "Signal",
    "Peer",
    "ReputationEvent",
    "IntentEvent",
    "FeedbackEvent",
    "FeedItem",
    "ChannelAdapter",
    "CellArchive",
}

EXPECTED_PATTERN_KINDS = {
    "phrase",
    "boolean",
    "regex",
    "semantic",
    "typed_template",
    "claim_template",
    "graph_pattern",
    "policy_trigger",
}

EXPECTED_VARIABLE_TYPES = {
    "word",
    "text",
    "time",
    "date",
    "number",
    "money",
    "entity",
    "url",
    "email",
    "location",
    "custom",
}

EXPECTED_FIXTURE_DOMAINS = {
    "weather_alert",
    "real_estate_listing",
    "market_offer",
    "competitor_release",
    "legal_public_hearing",
    "political_public_event",
    "github_repo_change",
    "regulatory_standard_change",
}

REQUIRED_RUNTIME_DOC_MARKERS = [
    "create cell -> configure cell -> add source -> add typed watch pattern",
    "cell.signal.v1/Signal.Ingest",
    "cell.intent.v1/IntentEvent.Append",
    "CellArchive.RestoreDryRun",
    "WatchPattern.Validate",
]

REQUIRED_LOOP_KEYS = {
    "schema_ref",
    "contract_id",
    "contract_version",
    "cell",
    "cell_config",
    "source",
    "watch",
    "watch_pattern",
    "signal",
    "feed_item",
    "intent_event",
    "feedback_event",
    "cell_archive",
}

REQUIRED_POSTGRES_TABLES = [
    "cell_cells",
    "cell_configs",
    "cell_sources",
    "cell_watches",
    "cell_watch_patterns",
    "cell_signals",
    "cell_feed_items",
    "cell_intent_events",
    "cell_feedback_events",
    "cell_archives",
]

REQUIRED_CLICKHOUSE_TABLES = [
    "cell_signal_scores",
    "cell_source_quality_facts",
    "cell_reputation_deltas",
    "cell_feedback_outcomes",
    "cell_watch_pattern_metrics",
    "cell_notification_metrics",
    "cell_social_environment_snapshots",
]

REQUIRED_POLICY_OPERATIONS = [
    "cell.create",
    "cell.configure",
    "source.create",
    "watch.create",
    "watch_pattern.create",
    "signal.ingest",
    "feed_item.emit",
    "intent_event.append",
    "feedback_event.record",
    "cell_archive.export",
]


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path) -> Any:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def require_keys(obj: dict[str, Any], keys: set[str], where: str) -> None:
    missing = sorted(k for k in keys if k not in obj)
    if missing:
        fail(f"missing keys in {where}: {', '.join(missing)}")


def enum_values(schema: dict[str, Any], def_name: str, prop_name: str) -> set[str]:
    try:
        values = schema["$defs"][def_name]["properties"][prop_name]["enum"]
    except KeyError as exc:
        fail(f"schema missing enum path $defs/{def_name}/properties/{prop_name}: {exc}")
    return set(values)


def validate_schema(schema: dict[str, Any]) -> None:
    if schema.get("$id") != "https://standards.socioprophet.org/schemas/personal-intelligence-cell.schema.json":
        fail("schema $id does not match normative Personal Intelligence Cell schema id")

    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        fail("schema missing $defs object")

    missing_defs = sorted(EXPECTED_DEFS - set(defs))
    if missing_defs:
        fail(f"schema missing required definitions: {', '.join(missing_defs)}")

    if enum_values(schema, "WatchPattern", "pattern_kind") != EXPECTED_PATTERN_KINDS:
        fail("WatchPattern.pattern_kind enum drifted from expected contract")

    if enum_values(schema, "PatternVariable", "type") != EXPECTED_VARIABLE_TYPES:
        fail("PatternVariable.type enum drifted from expected contract")

    for def_name in ["Signal", "FeedItem", "IntentEvent", "FeedbackEvent", "CellArchive"]:
        definition = defs[def_name]
        if definition.get("type") != "object":
            fail(f"{def_name} must be an object definition")
        if not definition.get("required"):
            fail(f"{def_name} must declare required fields")
        if definition.get("additionalProperties") is not False:
            fail(f"{def_name} must close over additionalProperties=false")

    signal_required = set(defs["Signal"]["required"])
    for required in ["evidence_refs", "novelty_score", "relevance_score", "confidence_score", "policy_status"]:
        if required not in signal_required:
            fail(f"Signal missing required field: {required}")

    intent_required = set(defs["IntentEvent"]["required"])
    for required in ["intent_text", "structured_intent", "policy_decision"]:
        if required not in intent_required:
            fail(f"IntentEvent missing required field: {required}")


def validate_fixture_pattern(fixture: dict[str, Any]) -> None:
    fixture_id = fixture.get("id", "<missing-id>")
    require_keys(
        fixture,
        {"id", "domain", "source", "watch_pattern", "input", "expected_extractions", "expected_signal"},
        fixture_id,
    )

    domain = fixture["domain"]
    if domain not in EXPECTED_FIXTURE_DOMAINS:
        fail(f"unexpected fixture domain {domain!r} in {fixture_id}")

    source = fixture["source"]
    if not isinstance(source, dict):
        fail(f"source must be object in {fixture_id}")
    require_keys(source, {"kind", "uri"}, f"{fixture_id}.source")

    pattern = fixture["watch_pattern"]
    if not isinstance(pattern, dict):
        fail(f"watch_pattern must be object in {fixture_id}")
    require_keys(pattern, {"pattern_kind", "raw_expression", "variables"}, f"{fixture_id}.watch_pattern")

    if pattern["pattern_kind"] not in {"typed_template", "claim_template"}:
        fail(f"fixture {fixture_id} must use typed_template or claim_template for deterministic extraction")

    variables = pattern["variables"]
    if not isinstance(variables, list) or not variables:
        fail(f"fixture {fixture_id} must declare at least one variable")

    names: list[str] = []
    for variable in variables:
        if not isinstance(variable, dict):
            fail(f"fixture {fixture_id} variable must be object")
        require_keys(variable, {"name", "type", "required"}, f"{fixture_id}.variable")
        name = variable["name"]
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            fail(f"fixture {fixture_id} variable has invalid name: {name!r}")
        if variable["type"] not in EXPECTED_VARIABLE_TYPES:
            fail(f"fixture {fixture_id} variable {name} has invalid type {variable['type']!r}")
        if not isinstance(variable["required"], bool):
            fail(f"fixture {fixture_id} variable {name} required must be boolean")
        names.append(name)

    raw_expression = pattern["raw_expression"]
    for name in names:
        if f"${name}" not in raw_expression:
            fail(f"fixture {fixture_id} variable ${name} not referenced in raw_expression")

    expected_extractions = fixture["expected_extractions"]
    if not isinstance(expected_extractions, dict):
        fail(f"fixture {fixture_id} expected_extractions must be object")
    extraction_keys = set(expected_extractions)
    unknown_extractions = sorted(extraction_keys - set(names))
    if unknown_extractions:
        fail(f"fixture {fixture_id} expected extractions not declared as variables: {', '.join(unknown_extractions)}")

    for variable in variables:
        if variable["required"] and variable["name"] not in extraction_keys:
            fail(f"fixture {fixture_id} missing expected extraction for required variable {variable['name']}")

    expected_signal = fixture["expected_signal"]
    if not isinstance(expected_signal, dict):
        fail(f"fixture {fixture_id} expected_signal must be object")
    require_keys(expected_signal, {"min_relevance_score", "requires_policy_gate", "requires_feed_item"}, f"{fixture_id}.expected_signal")

    score = expected_signal["min_relevance_score"]
    if not isinstance(score, (int, float)) or not 0 <= score <= 1:
        fail(f"fixture {fixture_id} min_relevance_score must be 0..1")
    if expected_signal["requires_policy_gate"] is not True:
        fail(f"fixture {fixture_id} must require policy gate")
    if expected_signal["requires_feed_item"] is not True:
        fail(f"fixture {fixture_id} must require feed item")


def validate_fixtures(fixtures_doc: dict[str, Any]) -> None:
    fixtures = fixtures_doc.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        fail("fixtures document must contain a non-empty fixtures list")

    seen_ids: set[str] = set()
    seen_domains: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            fail("each fixture must be an object")
        fixture_id = fixture.get("id")
        if fixture_id in seen_ids:
            fail(f"duplicate fixture id: {fixture_id}")
        seen_ids.add(fixture_id)
        seen_domains.add(fixture.get("domain"))
        validate_fixture_pattern(fixture)

    missing_domains = sorted(EXPECTED_FIXTURE_DOMAINS - seen_domains)
    if missing_domains:
        fail(f"missing required fixture domains: {', '.join(missing_domains)}")


def validate_runtime_doc() -> None:
    if not RUNTIME_DOC_PATH.exists():
        fail(f"missing runtime doc: {RUNTIME_DOC_PATH.relative_to(ROOT)}")
    text = RUNTIME_DOC_PATH.read_text(encoding="utf-8", errors="replace")
    for marker in REQUIRED_RUNTIME_DOC_MARKERS:
        if marker not in text:
            fail(f"runtime doc missing marker: {marker}")


def validate_loop_contract(loop: dict[str, Any]) -> None:
    require_keys(loop, REQUIRED_LOOP_KEYS, "loop contract")
    if loop["schema_ref"] != "https://standards.socioprophet.org/schemas/personal-intelligence-cell.schema.json":
        fail("loop contract schema_ref does not match Personal Intelligence Cell schema")

    cell = loop["cell"]
    config = loop["cell_config"]
    source = loop["source"]
    watch = loop["watch"]
    pattern = loop["watch_pattern"]
    signal = loop["signal"]
    feed = loop["feed_item"]
    intent = loop["intent_event"]
    feedback = loop["feedback_event"]
    archive = loop["cell_archive"]

    cell_id = cell.get("id")
    if not cell_id:
        fail("loop cell must have id")
    for section_name, section in [
        ("cell_config", config),
        ("watch", watch),
        ("signal", signal),
        ("feed_item", feed),
        ("intent_event", intent),
        ("feedback_event", feedback),
        ("cell_archive", archive),
    ]:
        if section.get("cell_id") != cell_id:
            fail(f"{section_name}.cell_id does not match cell.id")

    if source.get("id") not in watch.get("source_scope", []):
        fail("loop watch.source_scope must include source.id")
    if pattern.get("id") not in watch.get("pattern_refs", []):
        fail("loop watch.pattern_refs must include watch_pattern.id")
    if pattern.get("watch_id") != watch.get("id"):
        fail("loop watch_pattern.watch_id must match watch.id")
    if signal.get("source_id") != source.get("id"):
        fail("loop signal.source_id must match source.id")
    if signal.get("watch_id") != watch.get("id"):
        fail("loop signal.watch_id must match watch.id")
    if feed.get("signal_id") != signal.get("id"):
        fail("loop feed_item.signal_id must match signal.id")
    if feedback.get("signal_id") != signal.get("id"):
        fail("loop feedback_event.signal_id must match signal.id")

    if not signal.get("evidence_refs"):
        fail("loop signal must carry evidence_refs")
    for score_key in ["novelty_score", "relevance_score", "confidence_score", "source_trust_score"]:
        score = signal.get(score_key)
        if not isinstance(score, (int, float)) or not 0 <= score <= 1:
            fail(f"loop signal {score_key} must be numeric 0..1")

    policy_decision = feed.get("policy_decision")
    if not isinstance(policy_decision, dict) or policy_decision.get("decision") != "allow":
        fail("loop feed_item must include allow policy_decision")
    intent_policy = intent.get("policy_decision")
    if not isinstance(intent_policy, dict) or intent_policy.get("decision") != "allow":
        fail("loop intent_event must include allow policy_decision")
    if not intent.get("intent_text") or not intent.get("structured_intent"):
        fail("loop intent_event must include readable text and structured intent")
    if signal.get("id") not in intent.get("emitted_events", []):
        fail("loop intent_event.emitted_events must include signal id")
    if feed.get("id") not in intent.get("emitted_events", []):
        fail("loop intent_event.emitted_events must include feed item id")

    if feedback.get("action") != "mark_relevant":
        fail("loop feedback_event must mark the signal relevant")
    manifest = archive.get("manifest")
    if not isinstance(manifest, dict):
        fail("loop cell_archive.manifest must be object")
    for required_count in ["cells", "configs", "sources", "watches", "watch_patterns", "signals", "feed_items", "intent_events", "feedback_events"]:
        if manifest.get(required_count) != 1:
            fail(f"loop cell_archive.manifest must count one {required_count}")
    if not archive.get("restore_dry_run_report_ref"):
        fail("loop cell_archive must include restore_dry_run_report_ref")


def validate_persistence_artifacts() -> None:
    if not POSTGRES_MIGRATION_PATH.exists():
        fail(f"missing Postgres migration: {POSTGRES_MIGRATION_PATH.relative_to(ROOT)}")
    postgres_sql = POSTGRES_MIGRATION_PATH.read_text(encoding="utf-8", errors="replace")
    for table in REQUIRED_POSTGRES_TABLES:
        if f"CREATE TABLE IF NOT EXISTS {table}" not in postgres_sql:
            fail(f"Postgres migration missing table: {table}")
    for marker in ["body JSONB NOT NULL", "GENERATED ALWAYS AS", "policy_decision JSONB GENERATED ALWAYS AS", "restore_dry_run_report_ref TEXT GENERATED ALWAYS AS"]:
        if marker not in postgres_sql:
            fail(f"Postgres migration missing body-first marker: {marker}")

    if not CLICKHOUSE_SCHEMA_PATH.exists():
        fail(f"missing ClickHouse schema: {CLICKHOUSE_SCHEMA_PATH.relative_to(ROOT)}")
    clickhouse_sql = CLICKHOUSE_SCHEMA_PATH.read_text(encoding="utf-8", errors="replace")
    for table in REQUIRED_CLICKHOUSE_TABLES:
        if f"CREATE TABLE IF NOT EXISTS {table}" not in clickhouse_sql:
            fail(f"ClickHouse schema missing table: {table}")
    for marker in ["MergeTree", "cell_signal_scores", "cell_social_environment_snapshots"]:
        if marker not in clickhouse_sql:
            fail(f"ClickHouse schema missing marker: {marker}")


def validate_policy_artifacts() -> None:
    if not POLICY_PATH.exists():
        fail(f"missing policy module: {POLICY_PATH.relative_to(ROOT)}")
    if not SERVICE_PATH.exists():
        fail(f"missing service module: {SERVICE_PATH.relative_to(ROOT)}")
    policy_text = POLICY_PATH.read_text(encoding="utf-8", errors="replace")
    service_text = SERVICE_PATH.read_text(encoding="utf-8", errors="replace")
    for marker in ["class PolicyEngine", "class StaticPolicyEngine", "def require_allowed"]:
        if marker not in policy_text:
            fail(f"policy module missing marker: {marker}")
    for operation in REQUIRED_POLICY_OPERATIONS:
        if operation not in service_text:
            fail(f"service missing policy operation gate: {operation}")
    for marker in ["policy_engine", "_require_allowed", "policy_decision"]:
        if marker not in service_text:
            fail(f"service missing policy marker: {marker}")


def main() -> None:
    schema = load_json(SCHEMA_PATH)
    fixtures = load_json(FIXTURES_PATH)
    loop = load_json(LOOP_CONTRACT_PATH)
    validate_schema(schema)
    validate_fixtures(fixtures)
    validate_runtime_doc()
    validate_loop_contract(loop)
    validate_persistence_artifacts()
    validate_policy_artifacts()
    print("OK: personal intelligence cell validation passed")


if __name__ == "__main__":
    main()
