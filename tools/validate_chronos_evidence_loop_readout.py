#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
READOUT = ROOT / "contracts" / "chronos-evidence-loop" / "customer-readout.v0.json"
REQUIRED_PLANES = {"Evidence", "Ontology", "Policy", "Agent carrier", "Ledger"}
REQUIRED_NON_CLAIMS = {
    "runtime execution",
    "provider calls",
    "external effects",
    "production storage",
    "patent or license",
    "downstream carrier ownership",
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("readout root must be an object")
    return data


def main() -> int:
    data = load(READOUT)
    if data.get("kind") != "chronos_evidence_loop_platform_readout":
        raise SystemExit("unexpected readout kind")
    if data.get("source_authority") != "SocioProphet/sociosphere":
        raise SystemExit("readout must name SocioSphere as source authority")
    if data.get("title") != "CHRONOS Evidence Loop":
        raise SystemExit("readout title must be CHRONOS Evidence Loop")

    boundary = data.get("platform_boundary", {})
    if boundary.get("read_only") is not True:
        raise SystemExit("platform readout must be read-only")
    if boundary.get("consumes_sociosphere_proof_package") is not True:
        raise SystemExit("platform readout must consume SocioSphere proof package")
    if boundary.get("owns_downstream_carriers") is not False:
        raise SystemExit("platform must not own downstream carriers")
    if boundary.get("executes_runtime_actions") is not False:
        raise SystemExit("platform readout must not execute runtime actions")

    planes = {item.get("plane") for item in data.get("carrier_planes", [])}
    if planes != REQUIRED_PLANES:
        raise SystemExit(f"carrier planes mismatch: {sorted(planes)}")

    non_claims = "\n".join(data.get("non_claims", [])).lower()
    missing = [term for term in REQUIRED_NON_CLAIMS if term not in non_claims]
    if missing:
        raise SystemExit("missing non-claim terms: " + ", ".join(sorted(missing)))

    if len(data.get("proof_points", [])) < 5:
        raise SystemExit("expected at least five proof points")

    print("OK: CHRONOS Evidence Loop platform readout validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
