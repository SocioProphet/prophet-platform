#!/usr/bin/env python3
"""Smoke test the fixture-backed Regis ACR API service.

The script imports the FastAPI app directly and exercises the minimum service path
without requiring a network listener. This keeps CI/local smoke deterministic while
still validating route behavior, safety posture, and receipt-shaped responses.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
APP_SRC = ROOT / "apps" / "regis-acr-api" / "src"
sys.path.insert(0, str(APP_SRC))

try:
    from fastapi.testclient import TestClient
    from regis_acr_api.main import app
except Exception as exc:  # pragma: no cover
    print(f"ERROR: failed to import regis_acr_api service: {exc}", file=sys.stderr)
    sys.exit(2)


def assert_receipt(payload: Dict[str, Any], action: str) -> None:
    receipt = payload.get("receipt")
    assert isinstance(receipt, dict), payload
    assert receipt.get("service") == "regis-acr-api", receipt
    assert receipt.get("action") == action, receipt
    assert receipt.get("status") == "succeeded", receipt
    for key in ("correlation_id", "subject_ref", "payload_ref", "event_ref", "receipt_ref", "created_at"):
        assert receipt.get(key), receipt


def main() -> int:
    client = TestClient(app)

    health = client.get("/healthz")
    assert health.status_code == 200, health.text
    health_json = health.json()
    assert health_json["ok"] is True, health_json
    assert health_json["service"] == "regis-acr-api", health_json
    assert "DecisionLedgerEntry" in health_json["contracts"], health_json

    source_record = {
        "source_record_id": "src:tesco:supplier:0001",
        "source_system": "tesco-supplier-master-demo",
        "entity_type": "organization",
        "raw_payload": {
            "name": "Acme Cooperative Foods Ltd",
            "supplier_number": "SUP-0001",
            "country": "GB",
        },
        "normalized_payload": {
            "name": "Acme Cooperative Foods Ltd",
            "supplier_number": "SUP-0001",
            "country": "GB",
        },
    }

    ingest = client.post("/v1/source-records", json=source_record)
    assert ingest.status_code == 200, ingest.text
    ingest_json = ingest.json()
    assert ingest_json["ok"] is True, ingest_json
    assert ingest_json["decision_ledger_entry"]["canonical_mutation"] is False, ingest_json
    assert ingest_json["decision_ledger_entry"]["outcome"] == "accepted_as_evidence_only", ingest_json
    assert_receipt(ingest_json, "SourceRecordIngest")

    proposal = client.post("/v1/concordance/proposals", json=source_record)
    assert proposal.status_code == 200, proposal.text
    proposal_json = proposal.json()
    assert proposal_json["concordance_links"][0]["status"] == "pending_review", proposal_json
    assert proposal_json["concordance_links"][0]["canonical_mutation"] is False, proposal_json
    assert proposal_json["decision_ledger_entry"]["canonical_mutation"] is False, proposal_json
    assert_receipt(proposal_json, "ConcordanceProposal")

    low_margin = client.post("/v1/promotion/evaluate", json={
        "candidate_id": "canonical:acme-cooperative-foods-ltd",
        "top_score": 0.86,
        "runnerup_score": 0.82,
        "winner_flip_rate": 0.2,
    })
    assert low_margin.status_code == 200, low_margin.text
    low_json = low_margin.json()
    assert low_json["energy_ledger_entry"]["promotion_allowed"] is False, low_json
    assert low_json["energy_ledger_entry"]["promotion_decision"] == "blocked_or_review_required", low_json
    assert low_json["energy_ledger_entry"]["canonical_mutation"] is False, low_json
    assert_receipt(low_json, "PromotionEvaluation")

    eligible = client.post("/v1/promotion/evaluate", json={
        "candidate_id": "canonical:acme-cooperative-foods-ltd",
        "top_score": 0.98,
        "runnerup_score": 0.80,
        "winner_flip_rate": 0.0,
    })
    assert eligible.status_code == 200, eligible.text
    eligible_json = eligible.json()
    assert eligible_json["energy_ledger_entry"]["promotion_allowed"] is True, eligible_json
    assert eligible_json["energy_ledger_entry"]["promotion_decision"] == "eligible_for_evidence_only_insert", eligible_json
    assert eligible_json["energy_ledger_entry"]["canonical_mutation"] is False, eligible_json
    assert_receipt(eligible_json, "PromotionEvaluation")

    hook = client.post("/v1/relationships/formation-hooks", json={
        "relationship_type": "supplier-of",
        "subject_entity_ref": "canonical:acme-cooperative-foods-ltd",
        "object_entity_ref": "canonical:tesco-plc",
    })
    assert hook.status_code == 200, hook.text
    hook_json = hook.json()
    bindings = hook_json["relationship_formation_hook"]["ontogenesis_bindings"]
    assert bindings["genesis_event_required"] is True, hook_json
    assert bindings["validity_interval_required"] is True, hook_json
    assert bindings["derivation_path_required"] is True, hook_json
    assert hook_json["relationship_formation_hook"]["canonical_mutation"] is False, hook_json
    assert_receipt(hook_json, "RelationshipFormationHook")

    summary = {
        "ok": True,
        "service": "regis-acr-api",
        "checks": [
            "health",
            "source_record_ingest",
            "concordance_proposal_pending_review",
            "promotion_low_margin_blocked",
            "promotion_evidence_only_eligible",
            "relationship_formation_hook_ontogenesis_binding",
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
