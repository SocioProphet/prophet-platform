#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

UNITS = {"consistent", "inconsistent", "unknown", "unchecked"}
PROMOTIONS = {"candidate", "proposed", "admitted", "rejected"}


def fail(msg: str) -> None:
    raise SystemExit(msg)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact")
    parser.add_argument("--expect-units")
    args = parser.parse_args()
    data = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    required = [
        "artifactType",
        "applicationMode",
        "candidateId",
        "methodFamily",
        "datasetRef",
        "equationLatex",
        "fitMetric",
        "complexity",
        "unitsStatus",
        "promotionState",
        "nonAuthorityDeclaration",
        "issuedAt",
    ]
    for key in required:
        if key not in data:
            fail(f"missing {key}")
    if data["artifactType"] != "EquationCandidate":
        fail("artifactType must be EquationCandidate")
    if data["applicationMode"] != "equation_discovery":
        fail("applicationMode must be equation_discovery")
    if data["methodFamily"] != "pysr":
        fail("methodFamily must be pysr")
    ds = data["datasetRef"]
    if not isinstance(ds, dict):
        fail("datasetRef must be object")
    if len(ds.get("contentHash", "")) != 64 or ds.get("hashAlgorithm") != "sha256":
        fail("datasetRef must carry sha256 content hash")
    if data["unitsStatus"] not in UNITS:
        fail("invalid unitsStatus")
    if args.expect_units and data["unitsStatus"] != args.expect_units:
        fail(f"expected unitsStatus {args.expect_units}, got {data['unitsStatus']}")
    if data["promotionState"] not in PROMOTIONS:
        fail("invalid promotionState")
    if data["unitsStatus"] == "inconsistent" and data["promotionState"] not in {"candidate", "rejected"}:
        fail("inconsistent units cannot be proposed/admitted")
    if "not a law" not in data["nonAuthorityDeclaration"]:
        fail("missing non-authority declaration")
    print(json.dumps({"valid": True, "candidateId": data["candidateId"], "unitsStatus": data["unitsStatus"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
