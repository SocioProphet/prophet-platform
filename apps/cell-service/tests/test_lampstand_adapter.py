from __future__ import annotations

import json
from pathlib import Path

import pytest

from cell_service import CellService, ServiceError
from cell_service.lampstand_adapter import LampstandIngestAdapter, LampstandAdapterError

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "schemas/cell/lampstand-ingest-fixture.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_lampstand_adapter_builds_source_and_signal_input() -> None:
    fixture = load_fixture()
    adapter = LampstandIngestAdapter()
    result = fixture["lampstand_result"]

    source = adapter.source_from_result(result)
    signal_input = adapter.signal_input_from_result(
        result,
        cell_id=fixture["cell"]["id"],
        watch_id=fixture["watch"]["id"],
    )

    assert source["kind"] == fixture["expected"]["source_kind"]
    assert source["policy_ref"] == fixture["expected"]["source_policy_ref"]
    assert source["provenance_profile"]["carrier_ref"] == fixture["expected"]["carrier_ref"]
    assert signal_input["signal_id"] == fixture["expected"]["signal_id"]
    assert signal_input["source_id"] == source["id"]
    assert len(signal_input["evidence_refs"]) >= fixture["expected"]["min_evidence_refs"]
    assert fixture["expected"]["carrier_ref"] in signal_input["text"]


def test_cell_service_ingests_lampstand_result() -> None:
    fixture = load_fixture()
    service = CellService()
    service.create_cell(fixture["cell"])
    service.create_watch(fixture["watch"])
    service.create_watch_pattern(fixture["watch_pattern"])

    signal = service.ingest_lampstand_result(
        fixture["lampstand_result"],
        cell_id=fixture["cell"]["id"],
        watch_id=fixture["watch"]["id"],
    )

    assert signal["id"] == fixture["expected"]["signal_id"]
    assert signal["extractions"]["carrier_ref"] == fixture["expected"]["carrier_ref"]
    assert signal["source_id"].startswith("source://lampstand/")
    assert len(signal["evidence_refs"]) >= fixture["expected"]["min_evidence_refs"]
    source = service.get_source(signal["source_id"])
    assert source["provenance_profile"]["carrier_ref"] == fixture["expected"]["carrier_ref"]


def test_cell_service_rejects_bad_lampstand_result() -> None:
    fixture = load_fixture()
    service = CellService()
    service.create_cell(fixture["cell"])
    service.create_watch(fixture["watch"])
    service.create_watch_pattern(fixture["watch_pattern"])

    bad = dict(fixture["lampstand_result"])
    bad["ok"] = False

    with pytest.raises(ServiceError, match="ok=true"):
        service.ingest_lampstand_result(bad, cell_id=fixture["cell"]["id"], watch_id=fixture["watch"]["id"])


def test_adapter_requires_entry_object() -> None:
    fixture = load_fixture()
    bad = dict(fixture["lampstand_result"])
    bad.pop("entry")

    with pytest.raises(LampstandAdapterError, match="entry object"):
        LampstandIngestAdapter().source_from_result(bad)
