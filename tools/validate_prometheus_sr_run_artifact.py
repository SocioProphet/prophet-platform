#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
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


def fail(message: str) -> None:
    raise SystemExit(message)


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail("root must be object")
    return data


def hex64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def canonical_payload(run: dict[str, Any]) -> bytes:
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


def validate(run: dict[str, Any]) -> None:
    for key in ["runId", "datasetRef", "methodFamily", "operatorLibrary", "randomSeed", "runtimeEnvironment", "replayHash", "controlAuthority", "candidateRefs", "chronosCarrierId", "issuedAt"]:
        if key not in run:
            fail(f"missing {key}")
    if run["methodFamily"] != "pysr":
        fail("methodFamily must be pysr for this platform emitter")
    ds = run["datasetRef"]
    if not isinstance(ds, dict) or not ds.get("uri") or not hex64(ds.get("contentHash")) or ds.get("hashAlgorithm") != "sha256":
        fail("invalid datasetRef")
    if not isinstance(run["operatorLibrary"].get("binaryOperators"), list):
        fail("operatorLibrary.binaryOperators must be array")
    if not isinstance(run["operatorLibrary"].get("unaryOperators"), list):
        fail("operatorLibrary.unaryOperators must be array")
    if not isinstance(run["operatorLibrary"].get("customOperators"), list):
        fail("operatorLibrary.customOperators must be array")
    if run["controlAuthority"] is not False:
        fail("controlAuthority must be false")
    candidates = run["candidateRefs"]
    if not isinstance(candidates, list) or not candidates:
        fail("candidateRefs must be non-empty array")
    for candidate in candidates:
        if candidate.get("unitsStatus") == "inconsistent" and candidate.get("promotionState") not in {"candidate", "rejected"}:
            fail("inconsistent units cannot be proposed/admitted")
    replay = run["replayHash"]
    if replay.get("algorithm") != "sha256" or replay.get("coveredFields") != HASH_FIELDS or not hex64(replay.get("value")):
        fail("invalid replayHash")
    computed = hashlib.sha256(canonical_payload(run)).hexdigest()
    if computed != replay["value"]:
        fail(f"replayHash mismatch: computed {computed}, expected {replay['value']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact")
    args = parser.parse_args()
    run = load(Path(args.artifact))
    validate(run)
    print(json.dumps({"valid": True, "replayHash": run["replayHash"]["value"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
