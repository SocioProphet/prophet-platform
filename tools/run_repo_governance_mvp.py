#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "contracts" / "repo-governance" / "examples" / "sociosphere-active-spine.observations.v0.json"
OUTPUT = ROOT / "build" / "repo-governance-mvp"


def load_packet() -> dict:
    return json.loads(INPUT.read_text(encoding="utf-8"))


def main() -> int:
    packet = load_packet()
    observations = packet["observations"]
    OUTPUT.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[dict]] = {}
    for obs in observations:
        grouped.setdefault(obs["subject_repository"], []).append(obs)

    findings = []
    policy_requests = []

    for repository, repo_observations in grouped.items():
        surfaces = {obs["surface"] for obs in repo_observations}
        observation_ids = [obs["observation_id"] for obs in repo_observations]

        if repository == "SocioProphet/hellgraph":
            findings.append({
                "schema_version": "0.1",
                "finding_id": "finding:hellgraph/promotion-ready",
                "rule_id": "repo-governance.active-spine-promotion-ready",
                "subject_repository": repository,
                "kind": "promotion-ready",
                "severity": "info",
                "antecedent_observations": observation_ids,
                "blockers": [],
                "policy_decision_required": true,
                "action_status": "policy_request_ready",
                "reason": "promotion candidate has complete governance surface coverage"
            })

            policy_requests.append({
                "schema_version": "0.1",
                "request_id": "policy-request:hellgraph/review",
                "finding_id": "finding:hellgraph/promotion-ready",
                "subject_repository": repository,
                "requested_decision": "review",
                "action_status": "policy_request_ready",
                "reason": "requires explicit policy review before any repository mutation"
            })

        if "corpus_loop_pin" in surfaces:
            findings.append({
                "schema_version": "0.1",
                "finding_id": "finding:corpus-loop/stale-pin",
                "rule_id": "repo-governance.corpus-loop-review",
                "subject_repository": "watson-cyc-semantic-web-chronos-v1",
                "kind": "stale-pin",
                "severity": "review",
                "antecedent_observations": observation_ids,
                "blockers": [],
                "policy_decision_required": true,
                "action_status": "advisory_only",
                "reason": "corpus loop pins require explicit governance review before refresh"
            })

    findings_path = OUTPUT / "repo-governance-findings.json"
    requests_path = OUTPUT / "repo-governance-policy-requests.json"

    findings_path.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    requests_path.write_text(json.dumps(policy_requests, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"OK: wrote {findings_path.relative_to(ROOT)}")
    print(f"OK: wrote {requests_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
