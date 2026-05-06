from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field

SERVICE_NAME = "regis-acr-api"
SERVICE_VERSION = "0.1.0"
DEFAULT_POLICY_ID = "policy://regis-acr/default-promotion@0.1.0"

app = FastAPI(title="Regis ACR API", version=SERVICE_VERSION)


class SourceRecordIngestRequest(BaseModel):
    source_record_id: str = Field(..., description="Stable source record id")
    source_system: str = Field(..., description="Source system or namespace")
    entity_type: str = Field(default="organization")
    raw_payload: Dict[str, Any]
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    policy_id: str = DEFAULT_POLICY_ID


class PromotionEvaluationRequest(BaseModel):
    candidate_id: str
    top_score: float
    runnerup_score: float = 0.0
    winner_flip_rate: float = 0.0
    policy_id: str = DEFAULT_POLICY_ID


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def receipt(action: str, subject_ref: str, status: str = "succeeded") -> Dict[str, Any]:
    correlation_id = f"regis-acr-{uuid4()}"
    created_at = now_iso()
    return {
        "correlation_id": correlation_id,
        "service": SERVICE_NAME,
        "action": action,
        "status": status,
        "subject_ref": subject_ref,
        "created_at": created_at,
        "payload_ref": f"artifact://prophet-platform/payloads/{SERVICE_NAME}/{correlation_id}.payload.json",
        "event_ref": f"artifact://prophet-platform/events/{SERVICE_NAME}/{correlation_id}.event.json",
        "receipt_ref": f"artifact://prophet-platform/receipts/{SERVICE_NAME}/{correlation_id}.receipt.json",
    }


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "contracts": [
            "CanonicalEntity",
            "SourceRecord",
            "ConcordanceLink",
            "EvidenceClaim",
            "DecisionLedgerEntry",
            "EnergyLedgerEntry",
            "PromotionPolicy",
            "RelationshipFormationHook",
        ],
    }


@app.post("/v1/source-records")
def ingest_source_record(req: SourceRecordIngestRequest) -> Dict[str, Any]:
    evidence_claim_id = f"evidenceclaim:{req.source_record_id}:primary"
    decision_id = f"decision:{req.source_record_id}:ingest"
    subject_ref = f"source-record://{req.source_system}/{req.source_record_id}"
    evidence_claim = {
        "evidence_claim_id": evidence_claim_id,
        "claim_type": "source_record_observed",
        "source_record_id": req.source_record_id,
        "entity_type": req.entity_type,
        "confidence": 1.0,
        "policy_id": req.policy_id,
        "created_at": now_iso(),
    }
    decision_ledger_entry = {
        "decision_id": decision_id,
        "decision_type": "source_record_ingested",
        "policy_id": req.policy_id,
        "evidence_claim_refs": [evidence_claim_id],
        "outcome": "accepted_as_evidence_only",
        "canonical_mutation": False,
        "reason_codes": ["evidence_does_not_overwrite_truth", "decision_receipt_required"],
    }
    return {
        "ok": True,
        "source_record_id": req.source_record_id,
        "evidence_claims": [evidence_claim],
        "decision_ledger_entry": decision_ledger_entry,
        "receipt": receipt("SourceRecordIngest", subject_ref),
    }


@app.post("/v1/concordance/proposals")
def propose_concordance(req: SourceRecordIngestRequest) -> Dict[str, Any]:
    entity_seed = req.normalized_payload.get("name") or req.raw_payload.get("name") or req.source_record_id
    candidate_entity_id = "canonical:" + str(entity_seed).lower().replace(" ", "-")
    link_id = f"concordance:{req.source_record_id}:{candidate_entity_id}"
    decision_id = f"decision:{req.source_record_id}:concordance-proposal"
    link = {
        "concordance_link_id": link_id,
        "source_record_id": req.source_record_id,
        "candidate_entity_id": candidate_entity_id,
        "status": "pending_review",
        "score": 0.86,
        "policy_id": req.policy_id,
        "canonical_mutation": False,
    }
    return {
        "ok": True,
        "concordance_links": [link],
        "decision_ledger_entry": {
            "decision_id": decision_id,
            "decision_type": "concordance_proposed",
            "policy_id": req.policy_id,
            "outcome": "pending_review",
            "canonical_mutation": False,
            "reason_codes": ["proposal_only", "no_auto_canonical_merge"],
        },
        "receipt": receipt("ConcordanceProposal", f"source-record://{req.source_system}/{req.source_record_id}"),
    }


@app.post("/v1/promotion/evaluate")
def evaluate_promotion(req: PromotionEvaluationRequest) -> Dict[str, Any]:
    margin = req.top_score - req.runnerup_score
    allowed = req.top_score >= 0.95 and margin >= 0.10 and req.winner_flip_rate <= 0.05
    outcome = "eligible_for_evidence_only_insert" if allowed else "blocked_or_review_required"
    return {
        "ok": True,
        "candidate_id": req.candidate_id,
        "policy_id": req.policy_id,
        "energy_ledger_entry": {
            "energy_ledger_id": f"energy:{req.candidate_id}:{uuid4()}",
            "top_score": req.top_score,
            "runnerup_score": req.runnerup_score,
            "margin_delta": margin,
            "winner_flip_rate": req.winner_flip_rate,
            "promotion_allowed": allowed,
            "promotion_decision": outcome,
            "canonical_mutation": False,
        },
        "decision_ledger_entry": {
            "decision_id": f"decision:{req.candidate_id}:promotion-evaluation",
            "decision_type": "promotion_evaluated",
            "policy_id": req.policy_id,
            "outcome": outcome,
            "canonical_mutation": False,
            "reason_codes": ["low_margin_blocks_promotion"] if not allowed else ["thresholds_satisfied", "evidence_only_first"],
        },
        "receipt": receipt("PromotionEvaluation", f"candidate://{req.candidate_id}"),
    }


@app.post("/v1/relationships/formation-hooks")
def emit_relationship_formation_hook(payload: Dict[str, Any]) -> Dict[str, Any]:
    hook_id = f"relationship-hook:{uuid4()}"
    return {
        "ok": True,
        "relationship_formation_hook": {
            "relationship_formation_hook_id": hook_id,
            "status": "proposed",
            "ontogenesis_bindings": {
                "genesis_event_required": True,
                "validity_interval_required": True,
                "derivation_path_required": True,
            },
            "payload": payload,
            "canonical_mutation": False,
        },
        "receipt": receipt("RelationshipFormationHook", hook_id),
    }
