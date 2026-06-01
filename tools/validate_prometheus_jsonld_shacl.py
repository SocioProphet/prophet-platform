#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from pyshacl import validate as run_shacl
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import XSD

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHAPES = ROOT / "contracts" / "ontology" / "sr-assertion.shacl.ttl"
SR = Namespace("https://socioprophet.github.io/ontogenesis/symbolic-regression#")

RESOURCES = {
    "sr:VocabularyDraftState": SR.VocabularyDraftState,
    "sr:VocabularyStabilizingState": SR.VocabularyStabilizingState,
    "sr:VocabularyCanonicalState": SR.VocabularyCanonicalState,
    "sr:ProposalCandidate": SR.ProposalCandidate,
    "sr:ProposalProposed": SR.ProposalProposed,
    "sr:ProposalAdmitted": SR.ProposalAdmitted,
    "sr:ProposalRejected": SR.ProposalRejected,
    "sr:ProposalFailureCorpus": SR.ProposalFailureCorpus,
    "sr:AdmissionPendingReview": SR.AdmissionPendingReview,
    "sr:AdmissionAdmitted": SR.AdmissionAdmitted,
    "sr:AdmissionRejected": SR.AdmissionRejected,
    "sr:AdmissionBlocked": SR.AdmissionBlocked,
    "sr:UnitsConsistent": SR.UnitsConsistent,
    "sr:UnitsInconsistent": SR.UnitsInconsistent,
    "sr:UnitsUnknown": SR.UnitsUnknown,
    "sr:UnitsUnchecked": SR.UnitsUnchecked,
}
TYPES = {
    "sr:DatasetEvidenceRef": SR.DatasetEvidenceRef,
    "sr:FitMetric": SR.FitMetric,
    "sr:ComplexityMetric": SR.ComplexityMetric,
    "sr:DimensionalAnalysisResult": SR.DimensionalAnalysisResult,
    "sr:EvidenceReplayRef": SR.EvidenceReplayRef,
    "sr:DiscoveryMethodRef": SR.DiscoveryMethodRef,
    "sr:SemanticReviewSurface": SR.SemanticReviewSurface,
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return data


def rid(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("@id", ""))
    return str(value)


def ref(value: str) -> URIRef:
    if value.startswith(("urn:", "http://", "https://")):
        return URIRef(value)
    return URIRef("urn:prometheus:local:" + value)


def sr(value: Any) -> URIRef:
    key = rid(value)
    if key not in RESOURCES:
        raise SystemExit(f"unknown sr id: {key}")
    return RESOURCES[key]


def child(graph: Graph, parent: URIRef, prop: URIRef, data: dict[str, Any], fallback: str) -> URIRef:
    n = ref(str(data.get("@id") or fallback))
    graph.add((parent, prop, n))
    typ = data.get("@type")
    if typ in TYPES:
        graph.add((n, RDF.type, TYPES[typ]))
    return n


def metric(graph: Graph, n: URIRef, data: dict[str, Any]) -> None:
    graph.add((n, SR.metricName, Literal(str(data["sr:metricName"]), datatype=XSD.string)))
    graph.add((n, SR.metricValue, Literal(Decimal(str(data["sr:metricValue"])), datatype=XSD.decimal)))


def graph_from(document: dict[str, Any]) -> Graph:
    g = Graph()
    g.bind("sr", SR)
    s = ref(str(document["@id"]))
    g.add((s, RDF.type, SR.SRAssertionProposal))
    g.add((s, SR.vocabVersion, Literal(str(document["sr:vocabVersion"]), datatype=XSD.string)))
    g.add((s, SR.vocabularyPromotionState, sr(document["sr:vocabularyPromotionState"])))
    g.add((s, SR.hasPromotionStatus, sr(document["sr:hasPromotionStatus"])))
    g.add((s, SR.hasAdmissionState, sr(document["sr:hasAdmissionState"])))
    g.add((s, SR.nonAuthorityDeclaration, Literal(str(document["sr:nonAuthorityDeclaration"]), datatype=XSD.string)))

    child(g, s, SR.hasDatasetEvidence, document["sr:hasDatasetEvidence"], "dataset")
    f = child(g, s, SR.hasFitMetric, document["sr:hasFitMetric"], "fit")
    metric(g, f, document["sr:hasFitMetric"])
    c = child(g, s, SR.hasComplexityMetric, document["sr:hasComplexityMetric"], "complexity")
    metric(g, c, document["sr:hasComplexityMetric"])
    d = child(g, s, SR.hasDimensionalAnalysis, document["sr:hasDimensionalAnalysis"], "dimension")
    g.add((d, SR.hasUnitsStatus, sr(document["sr:hasDimensionalAnalysis"]["sr:hasUnitsStatus"])))
    child(g, s, SR.hasEvidenceReplay, document["sr:hasEvidenceReplay"], "replay")
    child(g, s, SR.hasDiscoveryMethod, document["sr:hasDiscoveryMethod"], "method")
    surface = child(g, s, SR.hasSemanticReviewSurface, document["sr:hasSemanticReviewSurface"], "surface")
    g.add((surface, SR.reviewSurfaceType, Literal(str(document["sr:hasSemanticReviewSurface"]["sr:reviewSurfaceType"]))))
    return g


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document")
    parser.add_argument("--shapes", default=str(DEFAULT_SHAPES))
    args = parser.parse_args()
    conforms, _report_graph, report_text = run_shacl(
        data_graph=graph_from(load(Path(args.document))),
        shacl_graph=str(Path(args.shapes)),
        inference="rdfs",
        advanced=True,
    )
    if not conforms:
        print(report_text)
        raise SystemExit("SHACL validation failed")
    print(json.dumps({"valid": True, "document": args.document, "shapes": args.shapes}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
