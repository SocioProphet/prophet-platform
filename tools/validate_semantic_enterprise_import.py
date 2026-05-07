#!/usr/bin/env python3
"""Validate Prophet Platform's Semantic Enterprise v0.1 import contract.

The contract is platform-local. Ontogenesis remains the authored semantic source;
this validator proves the platform import membrane preserves the expected source,
scenario, query, named-graph, provenance, and closure surfaces.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = "contracts/semantic-enterprise/v0.1/semantic_enterprise_manifest.import.json"

REQUIRED_SCENARIOS = {
    "finance": "graphs/scenarios/finance-aml-kyc",
    "threat-intel": "graphs/scenarios/threat-intel-lifecycle",
    "investigation": "graphs/scenarios/investigation-custody",
    "supply-chain": "graphs/scenarios/supply-chain-resilience",
    "defense-c2": "graphs/scenarios/defense-c2-cop",
}

REQUIRED_PROVENANCE = {
    "source_path",
    "canonical_iri",
    "registry_reference",
    "validation_gate",
    "named_graph_uri",
    "trust_profile",
    "access_class",
}

REQUIRED_CLOSURE_KEYS = {
    "inside_source",
    "outside_runtime",
    "boundary_membrane",
    "feedback_surface",
}

REQUIRED_OUTPUTS = {
    "catalog_surface",
    "scenario_surface",
    "query_surface",
    "named_graph_surface",
}


def main() -> int:
    errors: list[str] = []
    path = ROOT / CONTRACT_PATH
    if not path.is_file():
        print(f"missing contract: {CONTRACT_PATH}")
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid JSON in {CONTRACT_PATH}: {exc}")
        return 1

    if data.get("contract") != "prophet-platform.semantic-enterprise.import":
        errors.append("unexpected contract identifier")
    if data.get("version") != "0.1.0":
        errors.append("unexpected contract version")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        expected_source = {
            "repository": "SocioProphet/ontogenesis",
            "release": "semantic-enterprise-v0.1.0",
            "manifest_path": "manifests/semantic_enterprise_v0_1_manifest.json",
            "rollup_registry_path": "catalog/semantic_enterprise_v0_1_registry.ttl",
            "release_note_path": "docs/semantic-enterprise/v0.1-release-note.md",
            "import_bridge_path": "docs/semantic-enterprise/downstream-import-bridge-v0.1.md",
        }
        for key, expected in expected_source.items():
            if source.get(key) != expected:
                errors.append(f"source.{key} expected {expected!r}, got {source.get(key)!r}")

    closure = data.get("closure_model")
    if not isinstance(closure, dict):
        errors.append("closure_model must be an object")
    else:
        missing = REQUIRED_CLOSURE_KEYS.difference(closure)
        if missing:
            errors.append(f"closure_model missing keys: {sorted(missing)}")
        for key in REQUIRED_CLOSURE_KEYS.intersection(closure):
            if not isinstance(closure.get(key), str) or not closure[key].strip():
                errors.append(f"closure_model.{key} must be a non-empty string")

    provenance = set(data.get("provenance_requirements") or [])
    missing_provenance = REQUIRED_PROVENANCE.difference(provenance)
    if missing_provenance:
        errors.append(f"missing provenance requirements: {sorted(missing_provenance)}")

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, dict):
        errors.append("scenarios must be an object")
    else:
        for name, graph_fragment in REQUIRED_SCENARIOS.items():
            spec = scenarios.get(name)
            if not isinstance(spec, dict):
                errors.append(f"missing scenario object: {name}")
                continue
            if not spec.get("scenario_path", "").startswith("examples/scenarios/"):
                errors.append(f"{name} scenario_path must point into examples/scenarios")
            if not spec.get("query_path", "").startswith("examples/queries/"):
                errors.append(f"{name} query_path must point into examples/queries")
            if spec.get("named_graph_uri_fragment") != graph_fragment:
                errors.append(f"{name} named graph fragment mismatch")

    if data.get("named_graph_fixture_path") != "examples/named-graphs/semantic_sector_named_graphs.ttl":
        errors.append("named_graph_fixture_path mismatch")

    outputs = data.get("platform_outputs")
    if not isinstance(outputs, dict):
        errors.append("platform_outputs must be an object")
    else:
        missing_outputs = REQUIRED_OUTPUTS.difference(outputs)
        if missing_outputs:
            errors.append(f"platform_outputs missing keys: {sorted(missing_outputs)}")

    consumers = set(data.get("downstream_consumers") or [])
    if "Prophet Platform" not in consumers:
        errors.append("downstream_consumers must include Prophet Platform")

    non_goals = set(data.get("non_goals") or [])
    if "live_ingestion" not in non_goals:
        errors.append("non_goals must include live_ingestion")

    if errors:
        print("Semantic Enterprise import contract validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Semantic Enterprise import contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
