#!/usr/bin/env python3
"""Tests for the RCA→HellGraph KnowledgeUpdate mapping (agent.v1, patch-nested)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rca_to_knowledge_update as k  # noqa: E402

_ADR = {"adr_id": "ADR-0001", "title": "Nix→Guix", "status": "parity",
        "from": {"lang": "nix"}, "to": {"lang": "guix"}}
_GRAPH = {"unported_count": 1, "unported": ["a.nix"],
          "nodes": [{"path": "a.nix", "depends_on": [], "ported": False, "waiver": None},
                    {"path": "b.nix", "depends_on": ["a.nix"], "ported": True, "waiver": None}]}


def test_shape_is_patch_nested_agent_v1():
    ku = k.to_knowledge_update(adr=_ADR, graph=_GRAPH)
    assert ku["schema"] == "agent.v1.KnowledgeUpdate" and ku["graph"] == "SYSTEM"
    assert "patch" in ku and "nodes" in ku["patch"] and "edges" in ku["patch"]  # NOT top-level


def test_adr_and_artifacts_become_nodes_with_scopes_edges():
    ku = k.to_knowledge_update(adr=_ADR, graph=_GRAPH)
    ids = {n["id"]: n for n in ku["patch"]["nodes"]}
    assert ids["adr:ADR-0001"]["kind"] == "ADR"
    assert "artifact:a.nix" in ids and ids["artifact:a.nix"]["attrs"]["residual"] is True
    assert ids["artifact:b.nix"]["attrs"]["residual"] is False
    scopes = [e for e in ku["patch"]["edges"] if e["rel"] == "scopes"]
    assert {e["to"] for e in scopes} == {"artifact:a.nix", "artifact:b.nix"}
    assert any(e["to"] == "artifact:a.nix" and e["severity"] == "residual" for e in scopes)


def test_dependency_edges_carry_the_stopgap_provenance():
    ku = k.to_knowledge_update(adr=_ADR, graph=_GRAPH)
    dep = [e for e in ku["patch"]["edges"] if e["rel"] == "dependsOn"]
    assert dep == [{"from": "artifact:a.nix", "rel": "dependsOn", "to": "artifact:b.nix",
                    "via": "regex-stopgap", "ts": dep[0]["ts"]}]


def test_wave1_violation_and_resolution_are_linked_to_the_adr():
    w1 = {"violations": [{"path": "new.nix", "rule": "no-new-FROM"}]}
    res = {"commons_id": "commons:governance/migration/resolution-ADR-0001@v0.1+abc",
           "asset_type": "resolution", "tags": ["nix", "guix"], "category": "dependency-swap-percolation"}
    ku = k.to_knowledge_update(adr=_ADR, graph=_GRAPH, wave1=w1, resolution=res)
    kinds = {n["kind"] for n in ku["patch"]["nodes"]}
    assert "GateViolation" in kinds and "ResolutionAsset" in kinds
    rels = {(e["from"].split(":")[0], e["rel"], e["to"]) for e in ku["patch"]["edges"]}
    assert ("violation", "violates", "adr:ADR-0001") in rels
    assert (res["commons_id"].split(":")[0], "resolves", "adr:ADR-0001") in {
        (e["from"].split(":")[0], e["rel"], e["to"]) for e in ku["patch"]["edges"]}


if __name__ == "__main__":
    fns = [v for x, v in sorted(globals().items()) if x.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"ok: {len(fns)} rca-to-knowledge-update tests passed")
    sys.exit(0)
