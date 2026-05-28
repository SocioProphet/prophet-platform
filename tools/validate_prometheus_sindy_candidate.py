#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate")
    args = parser.parse_args()
    data = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    required = [
        "artifactType",
        "applicationMode",
        "candidateId",
        "methodFamily",
        "implementationMode",
        "datasetRef",
        "equationLatex",
        "fitMetric",
        "complexity",
        "promotionState",
        "controlAuthority",
        "nonAuthorityDeclaration",
        "issuedAt",
    ]
    for key in required:
        if key not in data:
            fail(f"missing {key}")
    if data["artifactType"] != "PlatformDynamicsCandidate":
        fail("artifactType must be PlatformDynamicsCandidate")
    if data["applicationMode"] != "platform_dynamics":
        fail("applicationMode must be platform_dynamics")
    if data["methodFamily"] != "sindy":
        fail("methodFamily must be sindy")
    if data["implementationMode"] != "sindy_linear_fast_path":
        fail("implementationMode must be sindy_linear_fast_path")
    dataset_ref = data["datasetRef"]
    if len(dataset_ref.get("contentHash", "")) != 64 or dataset_ref.get("hashAlgorithm") != "sha256":
        fail("datasetRef must carry sha256 content hash")
    if data["controlAuthority"] is not False:
        fail("controlAuthority must be false")
    if data["promotionState"] != "candidate":
        fail("platform dynamics output must remain candidate")
    if "not an autoscaling policy" not in data["nonAuthorityDeclaration"]:
        fail("missing platform dynamics non-authority declaration")
    print(json.dumps({"valid": True, "candidateId": data["candidateId"], "controlAuthority": data["controlAuthority"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
