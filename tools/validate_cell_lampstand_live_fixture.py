#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/cell/lampstand-live/local-carrier.md"
RUNNER = ROOT / "tools/run_cell_lampstand_live_fixture.py"
LAMPSTAND_INGEST = ROOT / "apps/lampstand/src/prophet_platform_lampstand/ingest.py"
CELL_SERVICE = ROOT / "apps/cell-service/src/cell_service/service.py"
ADAPTER = ROOT / "apps/cell-service/src/cell_service/lampstand_adapter.py"


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
    fixture_text = require_file(FIXTURE)
    runner_text = require_file(RUNNER)
    lampstand_text = require_file(LAMPSTAND_INGEST)
    service_text = require_file(CELL_SERVICE)
    adapter_text = require_file(ADAPTER)

    require_markers(
        fixture_text,
        [
            "Lampstand Local Carrier Fixture",
            "SocioProphet/prophet-platform changed docs/PERSONAL_INTELLIGENCE_CELL_RUNTIME.md",
            "Lampstand carrier carrier://sha256/live-fixture ingested",
        ],
        "live Lampstand fixture",
    )
    require_markers(
        runner_text,
        [
            "prophet_platform_lampstand.ingest",
            "ingest_path",
            "CellService",
            "ingest_lampstand_result",
            "topic_ref=\"/cell/lampstand-live\"",
            "fixture:cell-lampstand-live",
            "evidence_ref_count",
            "analytics_snapshot",
        ],
        "live Lampstand fixture runner",
    )
    require_markers(
        lampstand_text,
        [
            "build_carrier_ingested",
            "evidence_receipt_ref",
            "publication_request",
        ],
        "Lampstand ingest wrapper",
    )
    require_markers(
        service_text,
        ["ingest_lampstand_result", "source_adapter", "lampstand-v1"],
        "cell service Lampstand integration",
    )
    require_markers(
        adapter_text,
        ["LampstandIngestAdapter", "evidence_refs_from_result", "carrier_ref"],
        "cell Lampstand adapter",
    )

    print("OK: live Lampstand fixture validation passed")


if __name__ == "__main__":
    main()
