#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "contracts" / "repo-governance" / "examples" / "sociosphere-active-spine.observations.v0.json"
OBSERVATION_SCHEMA = ROOT / "contracts" / "repo-governance" / "repo-governance-observation.v0.schema.json"
FINDING_SCHEMA = ROOT / "contracts" / "repo-governance" / "repo-governance-finding.v0.schema.json"
POLICY_REQUEST_SCHEMA = ROOT / "contracts" / "repo-governance" / "repo-governance-policy-request.v0.schema.json"
RUNNER = ROOT / "tools" / "run_repo_governance_mvp.py"


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    failed = False

    observation_schema = load_json(OBSERVATION_SCHEMA)
    finding_schema = load_json(FINDING_SCHEMA)
    policy_request_schema = load_json(POLICY_REQUEST_SCHEMA)
    observations = load_json(OBSERVATIONS)

    if observation_schema.get("title") != "Repo Governance Observation":
        fail("observation schema title mismatch")
        failed = True

    if finding_schema.get("title") != "Repo Governance Finding":
        fail("finding schema title mismatch")
        failed = True

    if policy_request_schema.get("title") != "Repo Governance Policy Request":
        fail("policy request schema title mismatch")
        failed = True

    observation_set = observations.get("observations", [])
    if len(observation_set) < 6:
        fail("expected at least 6 observations")
        failed = True

    surfaces = {obs["surface"] for obs in observation_set}
    required_surfaces = {
        "spine_registry",
        "manifest_overlay",
        "canonical_sources",
        "boundaries",
        "topology",
        "corpus_loop_pin",
    }

    missing_surfaces = required_surfaces - surfaces
    if missing_surfaces:
        fail(f"missing required surfaces: {sorted(missing_surfaces)}")
        failed = True

    runner_text = RUNNER.read_text(encoding="utf-8")
    required_tokens = [
        "promotion-ready",
        "policy_request_ready",
        "repo-governance.active-spine-promotion-ready",
        "repo-governance.corpus-loop-review",
    ]

    for token in required_tokens:
        if token not in runner_text:
            fail(f"runner missing token: {token}")
            failed = True

    if failed:
        return 1

    print("OK: repo governance MVP contracts validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
