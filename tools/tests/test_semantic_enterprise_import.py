from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/semantic-enterprise/v0.1/semantic_enterprise_manifest.import.json"


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_semantic_enterprise_contract_loads() -> None:
    data = load_contract()
    assert data["contract"] == "prophet-platform.semantic-enterprise.import"
    assert data["version"] == "0.1.0"
    assert data["source"]["repository"] == "SocioProphet/ontogenesis"
    assert data["source"]["release"] == "semantic-enterprise-v0.1.0"


def test_semantic_enterprise_has_all_sector_scenarios() -> None:
    data = load_contract()
    scenarios = data["scenarios"]
    assert set(scenarios) == {
        "finance",
        "threat-intel",
        "investigation",
        "supply-chain",
        "defense-c2",
    }
    for spec in scenarios.values():
        assert spec["scenario_path"].startswith("examples/scenarios/")
        assert spec["query_path"].startswith("examples/queries/")
        assert spec["named_graph_uri_fragment"].startswith("graphs/scenarios/")


def test_semantic_enterprise_preserves_boundary_and_provenance() -> None:
    data = load_contract()
    closure = data["closure_model"]
    assert set(closure) == {
        "inside_source",
        "outside_runtime",
        "boundary_membrane",
        "feedback_surface",
    }

    provenance = set(data["provenance_requirements"])
    assert {
        "source_path",
        "canonical_iri",
        "registry_reference",
        "validation_gate",
        "named_graph_uri",
        "trust_profile",
        "access_class",
    }.issubset(provenance)


def test_semantic_enterprise_platform_surfaces_are_named() -> None:
    data = load_contract()
    outputs = data["platform_outputs"]
    assert outputs["catalog_surface"] == "semantic-enterprise.catalog.v0.1"
    assert outputs["scenario_surface"] == "semantic-enterprise.scenario.v0.1"
    assert outputs["query_surface"] == "semantic-enterprise.query.v0.1"
    assert outputs["named_graph_surface"] == "semantic-enterprise.named-graph.v0.1"
