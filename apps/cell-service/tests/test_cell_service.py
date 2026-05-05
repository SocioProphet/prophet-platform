from __future__ import annotations

import json
from pathlib import Path

import pytest

from cell_service import CellService, ServiceError
from cell_service.policy import StaticPolicyEngine

ROOT = Path(__file__).resolve().parents[3]
LOOP_CONTRACT = ROOT / "contracts/cell/personal-intelligence-cell.loop.v1.example.json"


def load_loop() -> dict:
    return json.loads(LOOP_CONTRACT.read_text(encoding="utf-8"))


def test_health() -> None:
    service = CellService()
    health = service.health()
    assert health["service"] == "cell-service"
    assert health["status"] == "ok"
    assert health["policy"] == "StaticPolicyEngine"


def test_replay_loop_contract() -> None:
    service = CellService()
    result = service.run_loop_contract(load_loop())

    assert result["cell"]["id"] == "cell://demo/personal-intelligence-cell"
    assert result["watch_pattern"]["id"] in result["watch"]["pattern_refs"]
    assert result["signal"]["relevance_score"] >= 0.9
    assert result["signal"]["evidence_refs"]
    assert result["feed_item"]["policy_decision"]["decision"] == "allow"
    assert result["intent_event"]["policy_decision"]["decision"] == "allow"
    assert result["feedback_event"]["action"] == "mark_relevant"
    assert result["cell_archive"]["restore_dry_run_report_ref"]


def test_rejects_unknown_watch_pattern_variable_ref() -> None:
    service = CellService()
    loop = load_loop()
    service.create_cell(loop["cell"])
    service.create_source(loop["source"])
    service.create_watch(loop["watch"])
    bad_pattern = dict(loop["watch_pattern"])
    bad_pattern["frames"] = [{"order": 0, "variable_refs": ["missing"]}]

    with pytest.raises(ServiceError, match="unknown variable"):
        service.create_watch_pattern(bad_pattern)


def test_rejects_signal_without_evidence() -> None:
    service = CellService()
    loop = load_loop()
    service.create_cell(loop["cell"])
    service.create_source(loop["source"])
    service.create_watch(loop["watch"])
    service.create_watch_pattern(loop["watch_pattern"])
    bad_signal = dict(loop["signal"])
    bad_signal["evidence_refs"] = []

    with pytest.raises(ServiceError, match="evidence_refs"):
        service.ingest_signal(bad_signal)


def test_feed_policy_decision_is_generated_by_service() -> None:
    service = CellService()
    loop = load_loop()
    service.create_cell(loop["cell"])
    service.create_source(loop["source"])
    service.create_watch(loop["watch"])
    service.create_watch_pattern(loop["watch_pattern"])
    service.ingest_signal(loop["signal"])
    feed = dict(loop["feed_item"])
    feed.pop("policy_decision")

    emitted = service.emit_feed_item(feed)
    assert emitted["policy_decision"]["decision"] == "allow"
    assert emitted["policy_decision"]["policy_ref"] == feed["target_ref"]


def test_policy_denial_blocks_feed_emit() -> None:
    service = CellService(policy_engine=StaticPolicyEngine({"feed_item.emit": "deny"}))
    loop = load_loop()
    service.create_cell(loop["cell"])
    service.create_source(loop["source"])
    service.create_watch(loop["watch"])
    service.create_watch_pattern(loop["watch_pattern"])
    service.ingest_signal(loop["signal"])

    with pytest.raises(ServiceError, match="policy blocked feed_item.emit"):
        service.emit_feed_item(loop["feed_item"])


def test_policy_denial_blocks_archive_export() -> None:
    service = CellService(policy_engine=StaticPolicyEngine({"cell_archive.export": "review_required"}))
    loop = load_loop()
    service.create_cell(loop["cell"])

    with pytest.raises(ServiceError, match="policy blocked cell_archive.export"):
        service.export_cell_archive(loop["cell_archive"])


def test_ledger_like_source_must_be_disabled_by_default() -> None:
    service = CellService()
    source = {
        "id": "source://ledger/demo",
        "kind": "blockchain",
        "uri": "fixture://ledger",
        "trust_profile": {},
        "crawl_profile": {},
        "provenance_profile": {},
        "policy_ref": "policy://cell/demo/ledger",
        "enabled": True,
    }

    with pytest.raises(ServiceError, match="disabled by default"):
        service.create_source(source)
