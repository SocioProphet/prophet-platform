#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PINNED_SOURCE_REPO = "SocioProphet/agentplane"
PINNED_SOURCE_COMMIT = "fd99c38c52bb01ef8b0a401aeb5bca5e79970b20"
PINNED_SCHEMA_HASHES = {
    "schemas/agentplane/symbolic-regression/sr-run-artifact.schema.json": "7aeba269c09199e081da75a62c414cc571b3050196d596b21a6d768efec28cb3",
    "schemas/agentplane/symbolic-regression/sr-candidate-ref.schema.json": "41dac5d156690fc256465de11b5499826917df5cdc21c6833ce28eafef164e4e",
}
SR_RUN_ARTIFACT_SCHEMA = "schemas/agentplane/symbolic-regression/sr-run-artifact.schema.json"
REQUIRED_RUN_FIELDS = {
    "runId",
    "datasetRef",
    "methodFamily",
    "operatorLibrary",
    "randomSeed",
    "runtimeEnvironment",
    "replayHash",
    "controlAuthority",
    "candidateRefs",
    "chronosCarrierId",
    "issuedAt",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"expected JSON object: {path}")
    return data


def validate_schema_pins(root: Path) -> None:
    for rel_path, expected_hash in PINNED_SCHEMA_HASHES.items():
        path = root / rel_path
        if not path.exists():
            fail(f"missing pinned schema: {rel_path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            fail(f"schema pin drift: {rel_path}: {actual_hash} != {expected_hash}")
        load_json(path)


def load_method_family_enum(root: Path) -> frozenset[str]:
    schema = load_json(root / SR_RUN_ARTIFACT_SCHEMA)
    enum = schema.get("properties", {}).get("methodFamily", {}).get("enum", [])
    if not enum:
        fail(f"methodFamily enum missing from {SR_RUN_ARTIFACT_SCHEMA}")
    return frozenset(enum)


def validate_manifest_artifacts(root: Path, manifest_path: Path) -> None:
    method_family_enum = load_method_family_enum(root)
    manifest = load_json(manifest_path)
    runs = manifest.get("runs")
    if not isinstance(runs, list) or not runs:
        fail("manifest has no runs")
    for run in runs:
        run_artifact = root / run["runArtifact"]
        data = load_json(run_artifact)
        missing = REQUIRED_RUN_FIELDS - set(data)
        if missing:
            fail(f"{run_artifact}: missing fields {sorted(missing)}")
        if data["methodFamily"] not in method_family_enum:
            fail(f"{run_artifact}: methodFamily outside pinned enum")
        if data["methodFamily"] == "sindy" and data["controlAuthority"] is not False:
            fail(f"{run_artifact}: SINDy controlAuthority must be false")
        if not isinstance(data.get("candidateRefs"), list) or not data["candidateRefs"]:
            fail(f"{run_artifact}: candidateRefs must be non-empty")
        for candidate in data["candidateRefs"]:
            for field in ["candidateId", "equationLatex", "nmse", "complexity", "unitsStatus", "promotionState"]:
                if field not in candidate:
                    fail(f"{run_artifact}: candidateRef missing {field}")
            if candidate["unitsStatus"] == "inconsistent" and candidate["promotionState"] not in {"candidate", "rejected"}:
                fail(f"{run_artifact}: inconsistent units cannot be proposed/admitted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root)
    validate_schema_pins(root)
    validate_manifest_artifacts(root, Path(args.manifest))
    print(json.dumps({"valid": True, "sourceRepo": PINNED_SOURCE_REPO, "sourceCommit": PINNED_SOURCE_COMMIT}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
