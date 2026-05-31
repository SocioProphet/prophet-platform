#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts" / "ontology" / "prometheus-sr-assertion-compat.manifest.json"
EMITTER = ROOT / "tools" / "emit_prometheus_jsonld_review.py"
VALIDATOR = ROOT / "tools" / "validate_prometheus_jsonld_review.py"


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"expected object: {path}")
    return data


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_manifest(data: dict[str, Any]) -> None:
    if data.get("schemaVersion") != "prophet-platform.prometheus-ontogenesis-compat.v0.1":
        fail("schemaVersion mismatch")
    if data.get("recordType") != "PrometheusOntogenesisCompatibilityManifest":
        fail("recordType mismatch")
    if data.get("ontologyAuthority") != "SocioProphet/ontogenesis":
        fail("ontology authority mismatch")
    if data.get("platformConsumer") != "SocioProphet/prophet-platform":
        fail("platform consumer mismatch")
    if data.get("vocabVersion") != "0.1.0":
        fail("vocabVersion mismatch")
    boundary = data.get("authorityBoundary")
    if not isinstance(boundary, dict):
        fail("authorityBoundary must be object")
    for key in ("ontogenesisMutation", "assertionAdmission", "deploymentAuthorization", "webProtegeRequired"):
        if boundary.get(key) is not False:
            fail(f"authorityBoundary.{key} must be false")
    pinned = data.get("pinnedSources")
    if not isinstance(pinned, list) or len(pinned) != 2:
        fail("pinnedSources must contain vocab and shape entries")
    for source in pinned:
        if source.get("repo") != "SocioProphet/ontogenesis":
            fail("pinned source repo mismatch")
        blob = source.get("blobSha")
        if not isinstance(blob, str) or len(blob) != 40 or any(c not in "0123456789abcdef" for c in blob):
            fail("pinned source blobSha must be 40-char lowercase git SHA")
        terms = source.get("requiredTerms")
        if not isinstance(terms, list) or not terms:
            fail("pinned source requiredTerms must be non-empty")
    fields = data.get("requiredProposalFields")
    if not isinstance(fields, list) or "sr:hasAdmissionState" not in fields or "sr:nonAuthorityDeclaration" not in fields:
        fail("requiredProposalFields missing core fields")
    declaration = data.get("nonAuthorityDeclaration", "")
    if "does not" not in declaration:
        fail("nonAuthorityDeclaration must state non-authority")


def validate_platform_code(data: dict[str, Any]) -> None:
    emitter = text(EMITTER)
    validator = text(VALIDATOR)
    for field in data["requiredProposalFields"]:
        if field not in emitter and field not in validator:
            fail(f"platform code missing proposal field: {field}")
    for term in ("sr:SRAssertionProposal", "sr:VocabularyDraftState", "sr:AdmissionPendingReview", "sr:AdmissionBlocked", "automated_shacl_gate", "webprotege"):
        if term not in emitter and term not in validator:
            fail(f"platform code missing Ontogenesis term: {term}")
    if "does not mutate Ontogenesis" not in emitter:
        fail("emitter must preserve Ontogenesis non-mutation boundary")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(MANIFEST))
    args = parser.parse_args()
    data = load_json(Path(args.manifest))
    validate_manifest(data)
    validate_platform_code(data)
    print(json.dumps({"valid": True, "manifest": args.manifest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
