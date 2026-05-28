#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = {
    "@context",
    "@id",
    "@type",
    "sr:vocabVersion",
    "sr:vocabularyPromotionState",
    "sr:hasDatasetEvidence",
    "sr:hasFitMetric",
    "sr:hasComplexityMetric",
    "sr:hasDimensionalAnalysis",
    "sr:hasEvidenceReplay",
    "sr:hasDiscoveryMethod",
    "sr:hasPromotionStatus",
    "sr:hasAdmissionState",
    "sr:hasSemanticReviewSurface",
    "sr:nonAuthorityDeclaration",
    "sr:hasEquation",
    "prov:generatedAtTime",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"expected JSON object: {path}")
    return data


def id_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("@id", ""))
    return str(value)


def validate(document: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL - set(document)
    if missing:
        fail(f"missing fields: {sorted(missing)}")
    if document["@type"] != "sr:SRAssertionProposal":
        fail("@type must be sr:SRAssertionProposal")
    if document["sr:vocabVersion"] != "0.1.0":
        fail("vocabVersion must be 0.1.0")
    if id_value(document["sr:vocabularyPromotionState"]) != "sr:VocabularyDraftState":
        fail("vocabularyPromotionState must be draft")
    dim = document["sr:hasDimensionalAnalysis"]
    if not isinstance(dim, dict):
        fail("dimensional analysis must be object")
    units = id_value(dim.get("sr:hasUnitsStatus"))
    if units not in {"sr:UnitsConsistent", "sr:UnitsInconsistent", "sr:UnitsUnknown", "sr:UnitsUnchecked"}:
        fail("invalid units status")
    promotion = id_value(document["sr:hasPromotionStatus"])
    state = id_value(document["sr:hasAdmissionState"])
    if units == "sr:UnitsInconsistent":
        if promotion not in {"sr:ProposalCandidate", "sr:ProposalRejected", "sr:ProposalFailureCorpus"}:
            fail("inconsistent units cannot be proposed/admitted")
        if state not in {"sr:AdmissionRejected", "sr:AdmissionBlocked"}:
            fail("inconsistent units cannot be pending/admitted")
    replay = document["sr:hasEvidenceReplay"]
    if not isinstance(replay, dict) or not replay.get("@id"):
        fail("evidence replay ref is required")
    review_surface = document["sr:hasSemanticReviewSurface"]
    if not isinstance(review_surface, dict):
        fail("review surface must be object")
    surface_type = review_surface.get("sr:reviewSurfaceType")
    if surface_type not in {"automated_shacl_gate", "git_pr", "prophet_platform_ui", "cli", "sparql_editor", "webprotege"}:
        fail("invalid review surface")
    declaration = document["sr:nonAuthorityDeclaration"]
    if not isinstance(declaration, str) or "does not" not in declaration:
        fail("missing non-authority declaration")
    if not isinstance(document["sr:hasEquation"], str) or not document["sr:hasEquation"]:
        fail("equation string is required")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document")
    args = parser.parse_args()
    document = load_json(Path(args.document))
    validate(document)
    print(json.dumps({"valid": True, "document": args.document}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
