#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CATALOG = Path("contracts/prometheus/neurosymbolic-capability-catalog.v0.1.json")
ARTIFACTS = [
    Path("contracts/prometheus/neurosymbolic-run-artifact.ai-descartes.example.json"),
    Path("contracts/prometheus/neurosymbolic-run-artifact.fol-lnn.example.json"),
]

ALLOWED_PROMOTIONS = {"candidate", "proposed_for_review", "rejected", "failure_corpus"}
ALLOWED_REVIEW_SURFACES = {"automated_shacl_gate", "git_pr", "prophet_platform_ui", "cli", "sparql_editor", "webprotege"}
KNOWN_METHODS = {"ai_descartes", "lnn_truth_bounds", "amr_logic", "knowledge_substrate", "theorem_search", "symbolic_policy"}


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"{path}: expected JSON object")
    return data


def require_hash(value: Any, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
        fail(f"{label}: expected 64-character sha256 hex string")


def require_non_authority(text: Any, path: Path) -> None:
    if not isinstance(text, str):
        fail(f"{path}: nonAuthorityDeclaration must be string")
    lowered = text.lower()
    if "not " not in lowered and "does not" not in lowered and "do not" not in lowered:
        fail(f"{path}: nonAuthorityDeclaration must explicitly contain non-authority language")


def validate_catalog(path: Path) -> set[str]:
    catalog = load_json(path)
    if catalog.get("contractType") != "PrometheusNeuroSymbolicCapabilityCatalog":
        fail(f"{path}: contractType mismatch")
    if catalog.get("schemaVersion") != "0.1.0":
        fail(f"{path}: schemaVersion must be 0.1.0")
    source = catalog.get("sourcePolicy")
    if not isinstance(source, dict):
        fail(f"{path}: sourcePolicy must be object")
    if source.get("vendorDependency") is not False:
        fail(f"{path}: vendorDependency must be false")
    if source.get("runtimeVendoringApproved") is not False:
        fail(f"{path}: runtimeVendoringApproved must be false")
    require_non_authority(source.get("nonAuthorityDeclaration"), path)

    capabilities = catalog.get("capabilities")
    if not isinstance(capabilities, list) or len(capabilities) < 4:
        fail(f"{path}: expected at least four capabilities")

    method_families: set[str] = set()
    seen: set[str] = set()
    for item in capabilities:
        if not isinstance(item, dict):
            fail(f"{path}: capability must be object")
        cap_id = item.get("capabilityId")
        if not isinstance(cap_id, str) or not cap_id.startswith("prometheus.nsr."):
            fail(f"{path}: invalid capabilityId")
        if cap_id in seen:
            fail(f"{path}: duplicate capabilityId {cap_id}")
        seen.add(cap_id)
        method = item.get("methodFamily")
        if method not in KNOWN_METHODS:
            fail(f"{path}: unknown methodFamily {method}")
        method_families.add(method)
        if item.get("controlAuthority") is not False:
            fail(f"{path}: capability {cap_id} must set controlAuthority false")
        if item.get("executionPosture") not in {"optional_engine_pending_runtime_pin", "read_only_reference_pending_adapter"}:
            fail(f"{path}: invalid executionPosture for {cap_id}")
        for field in ("applicationModes", "candidateArtifactTypes", "requiredGates", "prohibitedPromotions"):
            if not isinstance(item.get(field), list) or not item[field]:
                fail(f"{path}: capability {cap_id} missing non-empty {field}")
        require_non_authority(item.get("nonAuthorityDeclaration"), path)

    boundary = catalog.get("globalBoundary")
    if not isinstance(boundary, dict):
        fail(f"{path}: globalBoundary must be object")
    for flag in ("controlAuthority", "finalAdmissionAllowed", "memoryPromotionAllowed", "ontologyMutationAllowed", "policyMutationAllowed"):
        if boundary.get(flag) is not False:
            fail(f"{path}: globalBoundary {flag} must be false")
    require_non_authority(boundary.get("nonAuthorityDeclaration"), path)
    return method_families


def evidence_ref(artifact: dict[str, Any], path: Path) -> dict[str, Any]:
    dataset = artifact.get("datasetRef")
    source = artifact.get("sourceEvidenceRef")
    ref = dataset if isinstance(dataset, dict) else source
    if not isinstance(ref, dict):
        fail(f"{path}: expected datasetRef or sourceEvidenceRef")
    require_hash(ref.get("contentHash"), f"{path}: evidence contentHash")
    if ref.get("hashAlgorithm") != "sha256":
        fail(f"{path}: evidence hashAlgorithm must be sha256")
    return ref


def validate_candidate(candidate: dict[str, Any], path: Path, method: str) -> None:
    if not isinstance(candidate.get("candidateId"), str) or not candidate["candidateId"].startswith("urn:prometheus:candidate:"):
        fail(f"{path}: invalid candidateId")
    if not isinstance(candidate.get("artifactType"), str):
        fail(f"{path}: candidate artifactType required")
    if candidate.get("promotionState") not in ALLOWED_PROMOTIONS:
        fail(f"{path}: invalid candidate promotionState")

    if method == "ai_descartes":
        if candidate.get("artifactType") not in {"EquationCandidate", "ProgramCandidate", "ExperimentProposal"}:
            fail(f"{path}: ai_descartes candidate type mismatch")
        if candidate.get("unitsStatus") != "consistent":
            fail(f"{path}: ai_descartes fixture must use consistent units")
        fit = candidate.get("fitMetric")
        if not isinstance(fit, dict) or fit.get("name") != "nmse":
            fail(f"{path}: ai_descartes candidate requires nmse fit metric")
        if not isinstance(candidate.get("complexity"), int) or candidate["complexity"] <= 0:
            fail(f"{path}: ai_descartes candidate complexity must be positive integer")

    if method == "lnn_truth_bounds":
        if candidate.get("artifactType") != "TruthBoundObservation":
            fail(f"{path}: lnn_truth_bounds candidate type mismatch")
        lower = candidate.get("truthLowerBound")
        upper = candidate.get("truthUpperBound")
        if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)) or not (0 <= lower <= upper <= 1):
            fail(f"{path}: invalid truth bound interval")
        if not candidate.get("truthRegionCalibrationRef"):
            fail(f"{path}: truthRegionCalibrationRef required")


def validate_artifact(path: Path, catalog_methods: set[str]) -> None:
    artifact = load_json(path)
    if artifact.get("artifactType") != "PrometheusNeuroSymbolicRunArtifact":
        fail(f"{path}: artifactType mismatch")
    if artifact.get("schemaVersion") != "0.1.0":
        fail(f"{path}: schemaVersion must be 0.1.0")
    method = artifact.get("methodFamily")
    if method not in catalog_methods:
        fail(f"{path}: methodFamily {method} is not declared in catalog")
    if artifact.get("engineMode") != "fixture_only":
        fail(f"{path}: first tranche must be fixture_only")
    evidence_ref(artifact, path)

    replay = artifact.get("replayHash")
    if not isinstance(replay, dict):
        fail(f"{path}: replayHash must be object")
    if replay.get("algorithm") != "sha256":
        fail(f"{path}: replayHash algorithm must be sha256")
    require_hash(replay.get("value"), f"{path}: replayHash")
    if replay.get("state") not in {"fixture_verified", "pending"}:
        fail(f"{path}: replayHash state invalid")

    if artifact.get("semanticReviewSurface") not in ALLOWED_REVIEW_SURFACES:
        fail(f"{path}: invalid semanticReviewSurface")
    if artifact.get("controlAuthority") is not False:
        fail(f"{path}: controlAuthority must be false")
    if artifact.get("finalAdmissionRequested") is not False:
        fail(f"{path}: finalAdmissionRequested must be false")
    if artifact.get("chronosGovernanceFlags") != []:
        fail(f"{path}: fixture must have no CHRONOS governance flags")
    if artifact.get("promotionState") not in ALLOWED_PROMOTIONS:
        fail(f"{path}: invalid artifact promotionState")
    require_non_authority(artifact.get("nonAuthorityDeclaration"), path)

    candidates = artifact.get("candidateRefs")
    if not isinstance(candidates, list) or not candidates:
        fail(f"{path}: candidateRefs must be non-empty")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            fail(f"{path}: candidate must be object")
        validate_candidate(candidate, path, method)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PROMETHEUS neuro-symbolic catalog and fixture artifacts")
    parser.add_argument("--catalog", default=str(CATALOG))
    parser.add_argument("--artifact", action="append", default=[str(p) for p in ARTIFACTS])
    args = parser.parse_args()

    catalog_methods = validate_catalog(Path(args.catalog))
    for artifact in args.artifact:
        validate_artifact(Path(artifact), catalog_methods)

    print(json.dumps({"valid": True, "catalog": args.catalog, "artifactCount": len(args.artifact)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
