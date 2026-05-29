#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "contracts" / "channel-governance"
HIGH_RISK_SINKS = {"confirmed_memory", "graph_edge", "claim_promotion", "policy_binding", "publication", "export", "high_consequence_execution"}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture must be an object: {path}")
    return data


def check(check_id: str, passed: bool, diagnostics: list[str] | None = None) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "diagnostics": diagnostics or []}


def semantic_diagnostics(data: dict[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    requested_sink = data["sink_decision"]["requested_sink"]
    decision = data["sink_decision"]["decision"]
    envelope = data["authority_envelope"]
    repair_refs = data["repair"].get("repair_event_refs", [])

    if requested_sink not in envelope["allowed_sinks"]:
        diagnostics.append(f"requested sink {requested_sink} is not allowed")
    if requested_sink in envelope["disallowed_sinks"]:
        diagnostics.append(f"requested sink {requested_sink} is explicitly disallowed")
    if requested_sink in envelope["requires_repair_for"] and not repair_refs:
        diagnostics.append(f"requested sink {requested_sink} requires repair refs")
    if requested_sink in HIGH_RISK_SINKS and decision == "allow":
        diagnostics.append(f"high-risk sink {requested_sink} cannot be allowed by this synthetic gate fixture")
    if data["interpretant"]["selected_ref"] not in data["interpretant"]["candidate_refs"]:
        diagnostics.append("selected interpretant must be one of candidate_refs")
    if not data.get("evidence_refs"):
        diagnostics.append("evidence_refs required")
    if not data.get("policy_decision_refs"):
        diagnostics.append("policy_decision_refs required")
    if not data.get("non_claims") and decision == "allow":
        diagnostics.append("allowed gate decisions require non_claims")
    return diagnostics


def validate_fixture(path: Path) -> list[dict[str, Any]]:
    data = load(path)
    results = [
        check(f"{path.name}:schema-version", data.get("schema_version") == "1.0"),
        check(f"{path.name}:gate-id", str(data.get("gate_id", "")).startswith("channel-runtime-gate:")),
        check(f"{path.name}:gate-class", data.get("gate_class") in {"ingest_gate", "collapse_gate", "memory_sink_gate", "graph_sink_gate", "projection_sink_gate", "action_sink_gate"}),
        check(f"{path.name}:source-channel", bool(data.get("source_channel", {}).get("known_confusability_modes"))),
        check(f"{path.name}:percept", bool(data.get("percept", {}).get("percept_ref"))),
        check(f"{path.name}:interpretant", data.get("interpretant", {}).get("selected_ref") in data.get("interpretant", {}).get("candidate_refs", [])),
        check(f"{path.name}:authority-envelope", bool(data.get("authority_envelope", {}).get("allowed_sinks"))),
        check(f"{path.name}:evidence", bool(data.get("evidence_refs"))),
        check(f"{path.name}:policy", bool(data.get("policy_decision_refs"))),
    ]
    diagnostics = semantic_diagnostics(data)
    actual = "fail" if diagnostics else "pass"
    expected = "fail" if ".rejected." in path.name or path.name.startswith("bad-") else "pass"
    results.append(check(f"{path.name}:semantic-expected-{expected}", actual == expected, diagnostics))
    return results


def main() -> int:
    results: list[dict[str, Any]] = []
    fixtures = sorted(FIXTURE_DIR.glob("runtime-gate.*.example.json"))
    if not fixtures:
        raise SystemExit("No channel runtime gate fixtures found")
    for path in fixtures:
        results.extend(validate_fixture(path))
    passed = all(item["passed"] for item in results)
    print(json.dumps({"validator": "prophet-platform.channel-runtime-gates.validator.v1", "passed": passed, "results": results}, indent=2, sort_keys=True))
    print(("PASS" if passed else "FAIL") + ": channel runtime gate fixtures")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
