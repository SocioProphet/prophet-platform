#!/usr/bin/env python3
"""RCA → HellGraph — pull the blast-radius graph + resolution into the graph for RCA *over the graph*.

Answers "do the logs get pulled into HellGraph for root-cause analytics over the graph?". It maps an
ADR blast-radius graph (+ its Wave-1 violations and the deposited Resolution asset) into HellGraph's
`agent.v1.KnowledgeUpdate` shape (`{schema, nodes:[{id,kind,attrs}], edges:[{from,rel,to,…}]}`), which
`bin/hellgraph-agent-ingest.mjs` ingests into the AtomSpace. Once in the graph, root cause is a
traversal (blast_radius / containment) — not a one-off script — and the Resolution asset is a node the
Recommendation/Next-Best-Action surface can find and reuse.

Honest boundary: the blast-radius EDGES are still the regex stopgap (GBRG's tree-sitter parser is real
but its `gbrg-napi` query surface is a stub — `blast_radius` returns `generated:false`), so those edges
carry `via:"regex-stopgap"` until GBRG's napi is wired to a frozen index (fenced Rust).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_knowledge_update(*, adr: dict, graph: dict, wave1: dict | None = None,
                        resolution: dict | None = None, graph_kind: str = "SYSTEM") -> dict:
    """Pure map: blast-radius graph → agent.v1.KnowledgeUpdate. Nodes = ADR + artifacts + resolution
    + violations; edges = dependsOn / scopes / resolves / violates."""
    ts = _now()
    adr_id = adr.get("adr_id", "ADR")
    adr_node = f"adr:{adr_id}"
    frm, to_ = adr.get("from", {}).get("lang", "from"), adr.get("to", {}).get("lang", "to")

    nodes = [{"id": adr_node, "kind": "ADR",
              "attrs": {"title": adr.get("title"), "from": frm, "to": to_,
                        "status": adr.get("status"), "residual": graph.get("unported_count")}}]
    edges = []
    unported = set(graph.get("unported", []))
    for n in graph.get("nodes", []):
        aid = f"artifact:{n['path']}"
        residual = n["path"] in unported
        nodes.append({"id": aid, "kind": f"{frm.title()}Artifact",
                      "attrs": {"ported": n.get("ported"), "waiver": n.get("waiver"),
                                "residual": residual}})
        edges.append({"from": adr_node, "rel": "scopes", "to": aid, "ts": ts,
                      "severity": "residual" if residual else "ok"})
        for dep in n.get("depends_on", []):
            edges.append({"from": f"artifact:{dep}", "rel": "dependsOn", "to": aid,
                          "via": "regex-stopgap", "ts": ts})

    for v in (wave1 or {}).get("violations", []):
        vid = f"violation:{v['path']}"
        nodes.append({"id": vid, "kind": "GateViolation",
                      "attrs": {"rule": v.get("rule"), "wave": 1}})
        edges.append({"from": vid, "rel": "violates", "to": adr_node, "severity": "block", "ts": ts})

    if resolution:
        rid = resolution.get("commons_id", "resolution:unknown")
        nodes.append({"id": rid, "kind": "ResolutionAsset",
                      "attrs": {"asset_type": resolution.get("asset_type"),
                                "tags": resolution.get("tags"),
                                "category": resolution.get("category")}})
        edges.append({"from": rid, "rel": "resolves", "to": adr_node, "ts": ts})

    return {"schema": "agent.v1.KnowledgeUpdate", "graph": graph_kind, "ts": ts,
            "patch": {"nodes": nodes, "edges": edges},
            "prov": {"producer": "rca_to_knowledge_update", "adr_id": adr_id}}


if __name__ == "__main__":
    import sys
    from pathlib import Path
    import adr_dependency_graph as adg

    adr = json.loads(Path("governance/adr/ADR-0001-nix-to-guix.json").read_text())
    root = str(Path.home() / "dev/source-os")
    graph = adg.build_dependency_graph(adr, root)
    w1 = adg.wave1_prevent(adr, ["packages/sourceos-shell/default.nix"], root=root)
    resolution = None
    try:
        import resolution_asset as ra
        w2 = adg.wave2_detect_heal(adr, graph)
        svg = ra.render_root_cause_svg(graph)
        resolution = ra.build_resolution_asset(adr=adr, graph=graph, wave1=w1, wave2=w2,
                                               rca_doc="docs/ADR_PERCOLATION.md", svg=svg)
    except Exception:
        pass
    ku = to_knowledge_update(adr=adr, graph=graph, wave1=w1, resolution=resolution)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts/hellgraph/adr-0001.ku.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ku, indent=2))
    print(json.dumps({"knowledge_update": str(out), "nodes": len(ku["patch"]["nodes"]),
                      "edges": len(ku["patch"]["edges"]), "schema": ku["schema"]}, indent=2))
