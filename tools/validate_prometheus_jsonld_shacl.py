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


def sr(value: Any) -> URIRef | None:
    key = rid(value)
    if key not in RESOURCES:
        return None
    return RESOURCES[key]


def child(graph: Graph, parent: URIRef, prop: URIRef, data: Any, fallback: str) -> URIRef | None:
    if not isinstance(data, dict):
        return None
    n = ref(str(data.get("@id") or fallback))
    graph.add((parent, prop, n))
    typ = data.get("@type")
    if typ in TYPES:
        graph.add((n, RDF.type, TYPES[typ]))
    return n


def metric(graph: Graph, n: URIRef, data: dict[str, Any]) -> None:
    if "sr:metricName" in data:
        graph.add((n, SR.metricName, Literal(str(data["sr:metricName"]), datatype=XSD.string)))
    if "sr:metricValue" in data:
        graph.add((n, SR.metricValue, Literal(Decimal(str(data["sr:metricValue"])), datatype=XSD.decimal)))


def add_resource_value(graph: Graph, subject: URIRef, prop: URIRef, value: Any) -> None:
    resource = sr(value)
    if resource is not None:
        graph.add((subject, prop, resource))


def add_literal_value(graph: Graph, subject: URIRef, prop: URIRef, value: Any) -> None:
    if value is not None:
        graph.add((subject, prop, Literal(str(value), datatype=XSD.string)))


def graph_from(document: dict[str, Any]) -> Graph:
    g = Graph()
    g.bind("sr", SR)
    s = ref(str(document.get("@id", "urn:prometheus:proposal:missing-id")))
    g.add((s, RDF.type, SR.SRAssertionProposal))
    add_literal_value(g, s, SR.vocabVersion, document.get("sr:vocabVersion"))
    add_resource_value(g, s, SR.vocabularyPromotionState, document.get("sr:vocabularyPromotionState"))
    add_resource_value(g, s, SR.hasPromotionStatus, document.get("sr:hasPromotionStatus"))
    add_resource_value(g, s, SR.hasAdmissionState, document.get("sr:hasAdmissionState"))
    add_literal_value(g, s, SR.nonAuthorityDeclaration, document.get("sr:nonAuthorityDeclaration"))

    child(g, s, SR.hasDatasetEvidence, document.get("sr:hasDatasetEvidence"), "dataset")
    f = child(g, s, SR.hasFitMetric, document.get("sr:hasFitMetric"), "fit")
    if f is not None:
        metric(g, f, document.get("sr:hasFitMetric", {}))
    c = child(g, s, SR.hasComplexityMetric, document.get("sr:hasComplexityMetric"), "complexity")
    if c is not None:
        metric(g, c, document.get("sr:hasComplexityMetric", {}))
    d = child(g, s, SR.hasDimensionalAnalysis, document.get("sr:hasDimensionalAnalysis"), "dimension")
    if d is not None and isinstance(document.get("sr:hasDimensionalAnalysis"), dict):
        units = sr(document["sr:hasDimensionalAnalysis"].get("sr:hasUnitsStatus"))
        if units is not None:
            g.add((d, SR.hasUnitsStatus, units))
    child(g, s, SR.hasEvidenceReplay, document.get("sr:hasEvidenceReplay"), "replay")
    child(g, s, SR.hasDiscoveryMethod, document.get("sr:hasDiscoveryMethod"), "method")
    surface = child(g, s, SR.hasSemanticReviewSurface, document.get("sr:hasSemanticReviewSurface"), "surface")
    if surface is not None and isinstance(document.get("sr:hasSemanticReviewSurface"), dict):
        review_surface = document["sr:hasSemanticReviewSurface"].get("sr:reviewSurfaceType")
        if review_surface is not None:
            g.add((surface, SR.reviewSurfaceType, Literal(str(review_surface))))
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
