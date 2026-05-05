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


def main() -> None:
    schema = load_json(SCHEMA_PATH)
    fixtures = load_json(FIXTURES_PATH)
    validate_schema(schema)
    validate_fixtures(fixtures)
    validate_runtime_doc()
    print("OK: personal intelligence cell validation passed")


if __name__ == "__main__":
    main()
