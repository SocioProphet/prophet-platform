#!/usr/bin/env python3
"""Tests for the Resolution asset (ARM/commons record + root-cause SVG)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import resolution_asset as ra  # noqa: E402

_ADR = {"adr_id": "ADR-0001", "title": "Nix→Guix",
        "from": {"lang": "nix"}, "to": {"lang": "guix"}}
_GRAPH = {"adr_id": "ADR-0001", "from": "nix", "to": "guix", "node_count": 3, "unported_count": 2,
          "graph_digest": "sha256:deadbeef", "unported": ["a.nix", "b.nix"],
          "nodes": [{"path": "a.nix", "depends_on": [], "dependents": ["b.nix"], "ported": False, "waiver": None},
                    {"path": "b.nix", "depends_on": ["a.nix"], "dependents": [], "ported": False, "waiver": None},
                    {"path": "c.nix", "depends_on": [], "dependents": [], "ported": True, "waiver": None}]}


def test_svg_is_wellformed_and_draws_nodes_and_edges():
    svg = ra.render_root_cause_svg(_GRAPH)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert svg.count("<rect") == 3 and "<line" in svg  # 3 nodes, at least one edge
    assert "ADR-0001" in svg


def test_empty_graph_renders_a_placeholder():
    svg = ra.render_root_cause_svg({"nodes": []})
    assert svg.startswith("<svg") and "empty graph" in svg


def test_resolution_asset_is_tagged_content_addressed_and_sealed():
    svg = ra.render_root_cause_svg(_GRAPH)
    a = ra.build_resolution_asset(adr=_ADR, graph=_GRAPH, wave1={"ok": False}, wave2={"residual": 2},
                                  rca_doc="docs/ADR_PERCOLATION.md", svg=svg)
    assert a["asset_type"] == "resolution" and a["category"] == "dependency-swap-percolation"
    assert a["commons_id"].startswith("commons:governance/migration/resolution-ADR-0001@")
    assert {"nix", "guix", "swap", "rca"} <= set(a["tags"])
    assert a["content"]["root_cause_graph_svg"] == svg
    assert a["reproducible"] is True and a["receipt_digest"].startswith("sha256:")


def test_same_inputs_give_the_same_citable_id():
    svg = ra.render_root_cause_svg(_GRAPH)
    a = ra.build_resolution_asset(adr=_ADR, graph=_GRAPH, wave1={"ok": False}, wave2={"residual": 2},
                                  rca_doc="d", svg=svg)
    b = ra.build_resolution_asset(adr=_ADR, graph=_GRAPH, wave1={"ok": False}, wave2={"residual": 2},
                                  rca_doc="d", svg=svg)
    assert a["commons_id"] == b["commons_id"]  # content-addressed, reproducible


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"ok: {len(fns)} resolution-asset tests passed")
    sys.exit(0)
