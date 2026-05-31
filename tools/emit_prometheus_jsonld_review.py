#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SR = "https://socioprophet.github.io/ontogenesis/symbolic-regression#"

UNITS_RESOURCE = {
    "consistent": "sr:UnitsConsistent",
    "inconsistent": "sr:UnitsInconsistent",
    "unknown": "sr:UnitsUnknown",
    "unchecked": "sr:UnitsUnchecked",
}
GATE_POLICY = {
    "minimumDatasetSize": 4,
    "nmseCeiling": 0.001,
    "complexityCeiling": 10,
    "requiredUnitsStatus": "consistent",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def find_candidate_ref(run_artifact: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    for ref in run_artifact.get("candidateRefs", []):
        if ref.get("candidateId") == candidate_id:
            return ref
    raise ValueError("run artifact does not reference candidateId")


def validate_gate_evaluation(gate: dict[str, Any], candidate_ref: dict[str, Any]) -> None:
    required = [
        "candidateId",
        "datasetSize",
        "nmse",
        "complexity",
        "unitsStatus",
        "replayHashVerified",
        "chronosGovernanceFlags",
        "requestedReviewSurface",
        "finalAdmissionRequested",
    ]
    missing = [field for field in required if field not in gate]
    if missing:
        raise ValueError(f"gate evaluation missing fields: {missing}")
    if gate["candidateId"] != candidate_ref["candidateId"]:
        raise ValueError("gate evaluation candidateId mismatch")
    if gate["datasetSize"] < GATE_POLICY["minimumDatasetSize"]:
        raise ValueError("gate evaluation datasetSize below threshold")
    if gate["nmse"] > GATE_POLICY["nmseCeiling"]:
        raise ValueError("gate evaluation nmse above threshold")
    if gate["complexity"] > GATE_POLICY["complexityCeiling"]:
        raise ValueError("gate evaluation complexity above threshold")
    if gate["unitsStatus"] != GATE_POLICY["requiredUnitsStatus"]:
        raise ValueError("gate evaluation unitsStatus is not consistent")
    if gate["replayHashVerified"] is not True:
        raise ValueError("gate evaluation requires verified replay hash")
    if gate["chronosGovernanceFlags"]:
        raise ValueError("gate evaluation contains CHRONOS governance flags")
    if gate["requestedReviewSurface"] != "automated_shacl_gate":
        raise ValueError("gate evaluation does not target automated_shacl_gate")
    if gate["finalAdmissionRequested"] is True:
        raise ValueError("automated gate cannot request final admission")


def require_gate_if_needed(candidate_ref: dict[str, Any], args: argparse.Namespace) -> dict[str, Any] | None:
    if args.review_surface != "automated_shacl_gate":
        return None
    if not args.gate_evaluation:
        raise ValueError("automated_shacl_gate requires --gate-evaluation")
    gate = load_json(Path(args.gate_evaluation))
    validate_gate_evaluation(gate, candidate_ref)
    return gate


def build_jsonld(candidate: dict[str, Any], run_artifact: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    candidate_ref = find_candidate_ref(run_artifact, candidate["candidateId"])
    units_status = candidate_ref["unitsStatus"]
    gate = require_gate_if_needed(candidate_ref, args)
    promotion_state = "sr:ProposalCandidate" if units_status == "inconsistent" else "sr:ProposalProposed"
    state = "sr:AdmissionBlocked" if units_status == "inconsistent" else "sr:AdmissionPendingReview"
    dataset_ref = run_artifact["datasetRef"]
    document = {
        "@context": {
            "sr": SR,
            "prov": "http://www.w3.org/ns/prov#",
            "xsd": "http://www.w3.org/2001/XMLSchema#"
        },
        "@id": args.review_id,
        "@type": "sr:SRAssertionProposal",
        "sr:vocabVersion": "0.1.0",
        "sr:vocabularyPromotionState": {"@id": "sr:VocabularyDraftState"},
        "sr:hasDatasetEvidence": {
            "@id": f"{args.review_id}/dataset",
            "@type": "sr:DatasetEvidenceRef",
            "sr:datasetUri": dataset_ref["uri"],
            "sr:metricName": "sha256",
            "sr:metricValue": dataset_ref["contentHash"]
        },
        "sr:hasFitMetric": {
            "@id": f"{args.review_id}/fit-metric",
            "@type": "sr:FitMetric",
            "sr:metricName": "nmse",
            "sr:metricValue": candidate_ref["nmse"]
        },
        "sr:hasComplexityMetric": {
            "@id": f"{args.review_id}/complexity",
            "@type": "sr:ComplexityMetric",
            "sr:metricName": "complexity",
            "sr:metricValue": candidate_ref["complexity"]
        },
        "sr:hasDimensionalAnalysis": {
            "@id": f"{args.review_id}/dimensional-analysis",
            "@type": "sr:DimensionalAnalysisResult",
            "sr:hasUnitsStatus": {"@id": UNITS_RESOURCE[units_status]}
        },
        "sr:hasEvidenceReplay": {
            "@id": run_artifact["runId"],
            "@type": "sr:EvidenceReplayRef",
            "sr:metricName": "replayHash",
            "sr:metricValue": run_artifact["replayHash"]["value"]
        },
        "sr:hasDiscoveryMethod": {
            "@id": f"{args.review_id}/method",
            "@type": "sr:DiscoveryMethodRef",
            "sr:methodFamily": run_artifact["methodFamily"]
        },
        "sr:hasPromotionStatus": {"@id": promotion_state},
        "sr:hasAdmissionState": {"@id": state},
        "sr:hasSemanticReviewSurface": {
            "@id": f"{args.review_id}/review-surface",
            "@type": "sr:SemanticReviewSurface",
            "sr:reviewSurfaceType": args.review_surface
        },
        "sr:nonAuthorityDeclaration": "This JSON-LD artifact is a semantic review proposal only. It does not mutate Ontogenesis, create a law, or grant runtime authority.",
        "sr:hasEquation": candidate_ref["equationLatex"],
        "prov:generatedAtTime": args.issued_at or now_utc()
    }
    if gate is not None:
        document["sr:hasAutomatedGateEvaluation"] = {
            "@id": gate["evaluationId"],
            "sr:policyId": gate.get("policyId"),
            "sr:decisionBoundary": "eligibility_only"
        }
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit PROMETHEUS JSON-LD semantic review artifact")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--run-artifact", required=True)
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--review-surface", default="cli")
    parser.add_argument("--gate-evaluation")
    parser.add_argument("--issued-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    candidate = load_json(Path(args.candidate))
    run_artifact = load_json(Path(args.run_artifact))
    document = build_jsonld(candidate, run_artifact, args)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "reviewId": args.review_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
