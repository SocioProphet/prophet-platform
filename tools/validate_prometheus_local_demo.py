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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = load(manifest_path)
    if manifest.get("kind") != "PrometheusLocalDemoManifest":
        fail("manifest kind mismatch")
    if "not laws" not in manifest.get("nonAuthorityDeclaration", ""):
        fail("manifest missing non-authority declaration")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 4:
        fail("manifest must contain exactly four artifacts")
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
    validate_candidate(Path(run_by_method["pysr"]["candidateArtifact"]), "EquationCandidate", "pysr")
    validate_run_artifact(Path(run_by_method["pysr"]["runArtifact"]), "pysr")
    validate_candidate(Path(run_by_method["sindy"]["candidateArtifact"]), "PlatformDynamicsCandidate", "sindy")
    validate_run_artifact(Path(run_by_method["sindy"]["runArtifact"]), "sindy")

    print(json.dumps({"valid": True, "manifest": str(manifest_path), "artifactCount": len(artifacts)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
