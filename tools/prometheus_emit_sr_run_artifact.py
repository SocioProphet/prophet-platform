#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HASH_FIELDS = [
    "datasetRef.uri",
    "datasetRef.contentHash",
    "methodFamily",
    "operatorLibrary.binaryOperators",
    "operatorLibrary.unaryOperators",
    "operatorLibrary.customOperators",
    "randomSeed",
    "runtimeEnvironment.packages",
    "candidateRefs[*].equationLatex",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def package_versions() -> list[dict[str, str]]:
    packages = [{"name": "python", "version": sys.version.split()[0]}]
    try:
        import sympy
        packages.append({"name": "sympy", "version": str(sympy.__version__)})
    except Exception:
        packages.append({"name": "sympy", "version": "unavailable"})
    return packages


def canonical_hash_payload(run: dict[str, Any]) -> bytes:
    payload = {
        "datasetRef": {
            "uri": run["datasetRef"]["uri"],
            "contentHash": run["datasetRef"]["contentHash"],
        },
        "methodFamily": run["methodFamily"],
        "operatorLibrary": {
            "binaryOperators": sorted(run["operatorLibrary"].get("binaryOperators", [])),
            "unaryOperators": sorted(run["operatorLibrary"].get("unaryOperators", [])),
            "customOperators": sorted(run["operatorLibrary"].get("customOperators", [])),
        },
        "randomSeed": run["randomSeed"],
        "runtimeEnvironment": {
            "packages": sorted(run["runtimeEnvironment"].get("packages", []), key=lambda p: (p.get("name", ""), p.get("version", "")))
        },
        "candidateRefs": sorted([c["equationLatex"] for c in run.get("candidateRefs", [])]),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_run_artifact(candidate: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    dataset_ref = candidate["datasetRef"]
    candidate_ref = {
        "candidateId": candidate["candidateId"],
        "equationLatex": candidate["equationLatex"],
        "nmse": candidate["fitMetric"]["value"],
        "complexity": candidate["complexity"],
        "unitsStatus": candidate["unitsStatus"],
        "promotionState": candidate["promotionState"],
    }
    run = {
        "runId": args.run_id,
        "datasetRef": {
            "uri": dataset_ref["uri"],
            "contentHash": dataset_ref["contentHash"],
            "hashAlgorithm": dataset_ref.get("hashAlgorithm", "sha256"),
        },
        "methodFamily": candidate.get("methodFamily", "pysr"),
        "operatorLibrary": {
            "binaryOperators": args.binary_operator,
            "unaryOperators": args.unary_operator,
            "customOperators": args.custom_operator,
        },
        "randomSeed": args.random_seed,
        "runtimeEnvironment": {
            "packages": package_versions(),
            "implementationMode": candidate.get("implementationMode", "unknown"),
        },
        "replayHash": {
            "value": "0" * 64,
            "algorithm": "sha256",
            "coveredFields": HASH_FIELDS,
        },
        "controlAuthority": False,
        "candidateRefs": [candidate_ref],
        "chronosCarrierId": args.chronos_carrier_id,
        "issuedAt": args.issued_at or now_utc(),
    }
    run["replayHash"]["value"] = hashlib.sha256(canonical_hash_payload(run)).hexdigest()
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit AgentPlane-compatible PROMETHEUS SRRunArtifact")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--chronos-carrier-id", required=True)
    parser.add_argument("--random-seed", type=int)
    parser.add_argument("--binary-operator", action="append", default=["+", "*", "-", "/"])
    parser.add_argument("--unary-operator", action="append", default=[])
    parser.add_argument("--custom-operator", action="append", default=[])
    parser.add_argument("--issued-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    candidate = load_json(Path(args.candidate))
    artifact = build_run_artifact(candidate, args)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "replayHash": artifact["replayHash"]["value"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
