#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOCIAL_PATH = ROOT / "apps/cell-service/src/cell_service/social_environment.py"
TEST_PATH = ROOT / "apps/cell-service/tests/test_social_environment.py"
CLICKHOUSE_SCHEMA = ROOT / "infra/datastores/clickhouse/cell/0001_personal_intelligence_cell_analytics.sql"


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def require_file(path: Path) -> str:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8", errors="replace")


def require_markers(text: str, markers: list[str], where: str) -> None:
    for marker in markers:
        if marker not in text:
            fail(f"{where} missing marker: {marker}")


def main() -> None:
    social_text = require_file(SOCIAL_PATH)
    test_text = require_file(TEST_PATH)
    schema_text = require_file(CLICKHOUSE_SCHEMA)

    require_markers(
        social_text,
        [
            "social_environment_snapshot",
            "reputation_delta_event",
            "anti_manipulation_assessment",
            "coordinated_amplification_flags",
            "relationship_hygiene_recommendations",
            "social_snapshot_fact",
            "reputation_delta_fact",
            "source_quality_fact",
            "possible_sybil_repetition",
            "coordinated_claim_amplification",
            "review_required",
        ],
        "cell social environment module",
    )
    require_markers(
        test_text,
        [
            "test_social_environment_snapshot_detects_hygiene_and_amplification",
            "test_reputation_delta_event_includes_anti_manipulation_and_components",
            "test_anti_manipulation_assessment_flags_repetition",
            "test_source_quality_fact_aggregates_feedback_and_scores",
            "test_reputation_requires_evidence",
        ],
        "cell social environment tests",
    )
    require_markers(
        schema_text,
        [
            "CREATE TABLE IF NOT EXISTS cell_source_quality_facts",
            "CREATE TABLE IF NOT EXISTS cell_reputation_deltas",
            "CREATE TABLE IF NOT EXISTS cell_social_environment_snapshots",
            "anti_manipulation_flags Array(String)",
            "coordinated_amplification_flags Array(String)",
        ],
        "ClickHouse social/reputation schema",
    )

    print("OK: cell social environment validation passed")


if __name__ == "__main__":
    main()
