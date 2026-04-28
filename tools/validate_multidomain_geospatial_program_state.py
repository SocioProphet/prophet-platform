#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_TOP = [
    "registry_id",
    "version",
    "status",
    "updated_at",
    "safety_boundary",
    "standards_authorities",
    "implementation_repos",
    "gaia_multidomain_records",
    "runtime_proofs",
    "active_blockers",
    "progress",
    "next_best_actions",
]
REQUIRED_RECORDS = {
    "SpaceAssetRecord",
    "EarthObservationProductRecord",
    "VesselTrackObservation",
    "TelemetryObservation",
    "AirTrackObservation",
    "SensitiveGeoPolicyRecord",
    "SensorObservationEnvelope",
    "MultiDomainFusionEvent",
}
REQUIRED_RUNTIME_IDS = {
    "runtime:stac-ingest:v0",
    "runtime:ais-ingest:v0",
    "runtime:adsb-ingest:v0",
    "runtime:sensorthings-ingest:v0",
    "runtime:telemetry-ingest:v0",
    "runtime:sensitive-geo-policy-eval:v0",
}
REQUIRED_STANDARDS = {
    "SocioProphet/prophet-platform-standards",
    "SocioProphet/socioprophet-standards-storage",
    "SocioProphet/socioprophet-standards-knowledge",
    "SocioProphet/socioprophet-agent-standards",
}
REQUIRED_IMPLEMENTATIONS = {
    "SocioProphet/prophet-platform",
    "SocioProphet/gaia-world-model",
    "SocioProphet/sociosphere",
    "SocioProphet/sherlock-search",
    "SocioProphet/agentplane",
    "SocioProphet/lattice-forge",
}


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path}: invalid JSON: {exc}")
    if not isinstance(data, dict):
        fail(f"{path}: expected top-level object")
    return data


def require_keys(obj: dict, keys: list[str], where: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        fail(f"{where}: missing required keys: {', '.join(missing)}")


def require_percent(value: object, where: str) -> None:
    if not isinstance(value, int):
        fail(f"{where}: expected integer percent")
    if value < 0 or value > 100:
        fail(f"{where}: percent out of range")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "registry/multidomain_geospatial_program_state.v1.json"
    if not path.exists():
        fail("missing registry/multidomain_geospatial_program_state.v1.json")
    data = load_json(path)
    require_keys(data, REQUIRED_TOP, "program_state")

    safety = data["safety_boundary"]
    if not isinstance(safety, dict):
        fail("safety_boundary must be object")
    for key in ["allowed_scope", "disallowed_scope", "default_runtime_posture"]:
        if key not in safety:
            fail(f"safety_boundary missing {key}")
    if "ungoverned targeting" not in safety.get("disallowed_scope", []):
        fail("safety_boundary must explicitly disallow ungoverned targeting")
    if "effects-linked execution without authority, policy, evidence, and audit" not in safety.get("disallowed_scope", []):
        fail("safety_boundary must explicitly disallow effects-linked execution without accountability")

    standards = {entry.get("repo") for entry in data["standards_authorities"] if isinstance(entry, dict)}
    missing_standards = sorted(REQUIRED_STANDARDS - standards)
    if missing_standards:
        fail(f"missing standards authorities: {', '.join(missing_standards)}")

    implementations = {entry.get("repo") for entry in data["implementation_repos"] if isinstance(entry, dict)}
    missing_impls = sorted(REQUIRED_IMPLEMENTATIONS - implementations)
    if missing_impls:
        fail(f"missing implementation repos: {', '.join(missing_impls)}")

    records = set(data["gaia_multidomain_records"])
    missing_records = sorted(REQUIRED_RECORDS - records)
    if missing_records:
        fail(f"missing GAIA multidomain records: {', '.join(missing_records)}")

    runtime_ids = {entry.get("runtime_id") for entry in data["runtime_proofs"] if isinstance(entry, dict)}
    missing_runtimes = sorted(REQUIRED_RUNTIME_IDS - runtime_ids)
    if missing_runtimes:
        fail(f"missing runtime proofs: {', '.join(missing_runtimes)}")
    for idx, runtime in enumerate(data["runtime_proofs"]):
        if not isinstance(runtime, dict):
            fail(f"runtime_proofs[{idx}] must be object")
        require_keys(runtime, ["runtime_id", "entrypoint", "input_fixture", "boundary_doc", "ci_workflow", "admission_state", "evidence_bundle", "negative_tests"], f"runtime_proofs[{idx}]")
        if runtime["admission_state"] != "candidate_not_admitted":
            fail(f"{runtime['runtime_id']}: runtime must remain candidate_not_admitted until Lattice admission is complete")
        if runtime["evidence_bundle"] is not True or runtime["negative_tests"] is not True:
            fail(f"{runtime['runtime_id']}: runtime must have evidence bundle and negative tests")

    progress = data["progress"]
    if not isinstance(progress, dict):
        fail("progress must be object")
    require_percent(progress.get("composite_standards_spec_percent"), "progress.composite_standards_spec_percent")
    require_percent(progress.get("composite_implementation_readiness_percent"), "progress.composite_implementation_readiness_percent")
    workstreams = progress.get("workstreams")
    if not isinstance(workstreams, dict):
        fail("progress.workstreams must be object")
    for name, value in workstreams.items():
        require_percent(value, f"progress.workstreams.{name}")

    actions = data["next_best_actions"]
    if not isinstance(actions, list) or len(actions) < 3:
        fail("next_best_actions must contain at least three actions")

    print("OK: multidomain geospatial program state is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
