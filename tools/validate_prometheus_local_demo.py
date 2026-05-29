#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"expected object: {path}")
    return data


def validate_candidate(path: Path, expected_kind: str, expected_method: str) -> None:
    data = load(path)
    if data.get("artifactType") != expected_kind:
        fail(f"{path}: expected artifactType {expected_kind}")
    if data.get("methodFamily") != expected_method:
        fail(f"{path}: expected methodFamily {expected_method}")
    if data.get("promotionState") not in {"candidate", "rejected"}:
        fail(f"{path}: invalid promotionState")
    if expected_method == "sindy" and data.get("controlAuthority") is not False:
        fail(f"{path}: SINDy controlAuthority must be false")
    if "not" not in data.get("nonAuthorityDeclaration", ""):
        fail(f"{path}: missing non-authority declaration")


def validate_run_artifact(path: Path, expected_method: str) -> None:
    data = load(path)
    if data.get("methodFamily") != expected_method:
        fail(f"{path}: expected methodFamily {expected_method}")
    if data.get("controlAuthority") is not False:
        fail(f"{path}: controlAuthority must be false")
    replay = data.get("replayHash", {})
    if replay.get("algorithm") != "sha256" or len(replay.get("value", "")) != 64:
        fail(f"{path}: invalid replayHash")


def validate_gate_evaluation(path: Path, candidate_path: Path) -> None:
    gate = load(path)
    candidate = load(candidate_path)
    if gate.get("candidateId") != candidate.get("candidateId"):
        fail(f"{path}: gate candidateId mismatch")
    if gate.get("requestedReviewSurface") != "automated_shacl_gate":
        fail(f"{path}: gate must target automated_shacl_gate")
    if gate.get("finalAdmissionRequested") is not False:
        fail(f"{path}: gate must not request final admission")
    if gate.get("replayHashVerified") is not True:
        fail(f"{path}: replay hash must be verified")
    if gate.get("chronosGovernanceFlags") != []:
        fail(f"{path}: CHRONOS flags must be empty")


def validate_jsonld(path: Path, gate_path: Path) -> None:
    data = load(path)
    gate = load(gate_path)
    if data.get("@type") != "sr:SRAssertionProposal":
        fail(f"{path}: expected sr:SRAssertionProposal")
    if data.get("sr:hasAutomatedGateEvaluation", {}).get("@id") != gate.get("evaluationId"):
        fail(f"{path}: automated gate evaluation reference mismatch")
    if data.get("sr:hasSemanticReviewSurface", {}).get("sr:reviewSurfaceType") != "automated_shacl_gate":
        fail(f"{path}: review surface must be automated_shacl_gate")
    if "does not" not in data.get("sr:nonAuthorityDeclaration", ""):
        fail(f"{path}: missing non-authority declaration")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = load(manifest_path)
    if manifest.get("kind") != "PrometheusLocalDemoManifest":
        fail("manifest kind mismatch")
    if manifest.get("manifestVersion") != "0.2.0":
        fail("manifestVersion must be 0.2.0")
    if "not laws" not in manifest.get("nonAuthorityDeclaration", ""):
        fail("manifest missing non-authority declaration")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 6:
        fail("manifest must contain exactly six artifacts")
    for artifact in artifacts:
        path = Path(artifact.get("path", ""))
        if not path.exists():
            fail(f"missing artifact: {path}")
        if sha256_file(path) != artifact.get("sha256"):
            fail(f"hash mismatch: {path}")
    runs = manifest.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        fail("manifest must contain exactly two runs")
    run_by_method = {run.get("methodFamily"): run for run in runs}
    if set(run_by_method) != {"pysr", "sindy"}:
        fail("manifest must include pysr and sindy runs")
    for method, run in run_by_method.items():
        if run.get("controlAuthority") is not False:
            fail(f"{method}: controlAuthority must be false")
    pysr = run_by_method["pysr"]
    sindy = run_by_method["sindy"]
    validate_candidate(Path(pysr["candidateArtifact"]), "EquationCandidate", "pysr")
    validate_run_artifact(Path(pysr["runArtifact"]), "pysr")
    validate_gate_evaluation(Path(pysr["gateEvaluationArtifact"]), Path(pysr["candidateArtifact"]))
    validate_jsonld(Path(pysr["jsonldArtifact"]), Path(pysr["gateEvaluationArtifact"]))
    validate_candidate(Path(sindy["candidateArtifact"]), "PlatformDynamicsCandidate", "sindy")
    validate_run_artifact(Path(sindy["runArtifact"]), "sindy")

    print(json.dumps({"valid": True, "manifest": str(manifest_path), "artifactCount": len(artifacts)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
