#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "schemas/cell/lampstand-ingest-fixture.json"
ADAPTER_PATH = ROOT / "apps/cell-service/src/cell_service/lampstand_adapter.py"
SERVICE_PATH = ROOT / "apps/cell-service/src/cell_service/service.py"
SMOKE_PATH = ROOT / "tools/smoke_cell_service_loop.py"
TEST_PATH = ROOT / "apps/cell-service/tests/test_lampstand_adapter.py"


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


def require_keys(obj: dict[str, Any], keys: list[str], where: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        fail(f"missing keys in {where}: {', '.join(missing)}")


def validate_fixture() -> None:
    fixture = load_json(FIXTURE_PATH)
    require_keys(fixture, ["fixture_id", "lampstand_result", "cell", "watch", "watch_pattern", "expected"], "Lampstand fixture")
    result = fixture["lampstand_result"]
    require_keys(result, ["ok", "carrier_ref", "entry", "publication_request"], "Lampstand result")
    if result["ok"] is not True:
        fail("Lampstand fixture result must have ok=true")
    entry = result["entry"]
    require_keys(entry, ["service_ref", "event_type", "subject_ref", "scope_ref", "zone_ref", "receipt_ref", "payload_ref", "correlation_id", "classifiers"], "Lampstand entry")
    if entry["service_ref"] != "apps/lampstand":
        fail("Lampstand fixture entry.service_ref must be apps/lampstand")
    if entry["event_type"] != "carrier.ingested":
        fail("Lampstand fixture entry.event_type must be carrier.ingested")
    if fixture["watch_pattern"].get("raw_expression") != "Lampstand carrier $carrier_ref ingested":
        fail("Lampstand fixture watch pattern must capture carrier_ref")
    expected = fixture["expected"]
    require_keys(expected, ["source_kind", "source_policy_ref", "signal_id", "carrier_ref", "min_evidence_refs"], "Lampstand expected block")


def validate_code_markers() -> None:
    for path in [ADAPTER_PATH, SERVICE_PATH, SMOKE_PATH, TEST_PATH]:
        if not path.exists():
            fail(f"missing required file: {path.relative_to(ROOT)}")
    adapter_text = ADAPTER_PATH.read_text(encoding="utf-8", errors="replace")
    service_text = SERVICE_PATH.read_text(encoding="utf-8", errors="replace")
    smoke_text = SMOKE_PATH.read_text(encoding="utf-8", errors="replace")
    test_text = TEST_PATH.read_text(encoding="utf-8", errors="replace")

    for marker in ["class LampstandIngestAdapter", "source_from_result", "signal_input_from_result", "evidence_refs_from_result"]:
        if marker not in adapter_text:
            fail(f"Lampstand adapter missing marker: {marker}")
    for marker in ["ingest_lampstand_result", "source_adapter", "lampstand-v1", "LampstandIngestAdapter"]:
        if marker not in service_text:
            fail(f"cell service missing Lampstand marker: {marker}")
    for marker in ["LAMPSTAND_FIXTURE", "ingest_lampstand_result", "Lampstand adapter"]:
        if marker not in smoke_text:
            fail(f"cell smoke missing Lampstand marker: {marker}")
    for marker in ["test_cell_service_ingests_lampstand_result", "test_lampstand_adapter_builds_source_and_signal_input"]:
        if marker not in test_text:
            fail(f"Lampstand adapter tests missing marker: {marker}")


def main() -> None:
    validate_fixture()
    validate_code_markers()
    print("OK: cell Lampstand adapter validation passed")


if __name__ == "__main__":
    main()
