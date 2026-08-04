#!/usr/bin/env python3
"""Resolution asset — an RCA becomes a first-class, tagged, reusable ARM/commons asset (with SVG).

The miss this closes: a root-cause analysis was written as a markdown doc, not captured as a
**Resolution asset** in the Asset-Reuse-Manager sense — content-addressed, tagged, indexed, with the
root-cause graph rendered as **SVG**, so the next time the same failure class appears the resolution
is *found and reused* (ARM: Domain → Category → Asset → Recommendation → Feedback).

This produces exactly that from an ADR blast-radius graph (see adr_dependency_graph.py):
  * `render_root_cause_svg(graph)` — a real, dependency-only SVG (nodes laid out by depth, edges as
    arrows, unported/residual nodes highlighted). No deps; stdlib only.
  * `build_resolution_asset(...)` — a commons-shaped deposit record (`asset_type="resolution"`,
    content-addressed citable id `commons:<domain>/<name>@<version>+<digest>`, tags, reuse history,
    sealed) whose content carries the RCA + the SVG + the remediation plan.

The graph/edges here are a stopgap regex source; the real edges come from **GBRG** (tree-sitter,
`gbrg-napi`) and the asset should be deposited into the continuum **commons** and ingested into
**HellGraph** (`hellgraph-agent-ingest`) — this module is the shape those wire to.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(obj) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _depths(nodes: dict) -> dict:
    """Longest-path depth per node over the in-scope dependency edges (cycle-safe)."""
    memo: dict[str, int] = {}

    def d(p, stack):
        if p in memo:
            return memo[p]
        if p in stack:  # cycle guard
            return 0
        deps = [x for x in nodes[p]["depends_on"] if x in nodes]
        memo[p] = 0 if not deps else 1 + max(d(x, stack | {p}) for x in deps)
        return memo[p]

    for p in nodes:
        d(p, set())
    return memo


def render_root_cause_svg(graph: dict, *, max_label: int = 26) -> str:
    """Render the blast-radius graph as an SVG: columns = dependency depth, unported = red, ported =
    green, waived = grey. Arrows are `depends_on` edges. Theme-neutral, self-contained."""
    nodes = {n["path"]: n for n in graph.get("nodes", [])}
    if not nodes:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="60"><text x="12" y="34">empty graph</text></svg>'
    depth = _depths(nodes)
    cols: dict[int, list] = {}
    for p in sorted(nodes):
        cols.setdefault(depth[p], []).append(p)

    bw, bh, hgap, vgap, pad, top = 210, 30, 90, 14, 24, 90
    pos: dict[str, tuple] = {}
    for c in sorted(cols):
        for i, p in enumerate(cols[c]):
            pos[p] = (pad + c * (bw + hgap), top + i * (bh + vgap))
    width = pad * 2 + (max(cols) + 1) * (bw + hgap) - hgap
    height = top + max(len(v) for v in cols.values()) * (bh + vgap) + pad

    def color(n):
        if n.get("waiver"):
            return "#9aa4bb"
        return "#e2703a" if not n.get("ported") else "#3aa87a"

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'font-family="system-ui,sans-serif" font-size="12">',
             '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
             '<path d="M0,0 L7,3 L0,6 Z" fill="#6b7488"/></marker></defs>',
             f'<text x="{pad}" y="30" font-size="18" font-weight="700">Root-cause / blast-radius — '
             f'{_esc(graph.get("adr_id",""))}</text>',
             f'<text x="{pad}" y="52" fill="#6b7488">{graph.get("node_count",0)} nodes · '
             f'{graph.get("unported_count",0)} residual (red) · ported (green) · waived (grey) · '
             f'{graph.get("from","")}→{graph.get("to","")}</text>']
    # edges first (behind boxes)
    for p, n in nodes.items():
        x2, y2 = pos[p]
        for dep in n["depends_on"]:
            if dep in pos:
                x1, y1 = pos[dep]
                parts.append(f'<line x1="{x1+bw}" y1="{y1+bh//2}" x2="{x2}" y2="{y2+bh//2}" '
                             f'stroke="#6b7488" stroke-width="1" marker-end="url(#a)"/>')
    for p, n in nodes.items():
        x, y = pos[p]
        label = p.rsplit("/", 1)[-1]
        label = label if len(label) <= max_label else label[:max_label - 1] + "…"
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="5" fill="none" '
                     f'stroke="{color(n)}" stroke-width="2"/>'
                     f'<text x="{x+8}" y="{y+19}" fill="{color(n)}">{_esc(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def build_resolution_asset(*, adr: dict, graph: dict, wave1: dict, wave2: dict,
                           rca_doc: str, svg: str, domain: str = "governance/migration",
                           version: str = "v0.1") -> dict:
    """A commons/ARM-shaped Resolution asset: content-addressed, tagged, sealed, with reuse history."""
    name = f"resolution-{adr.get('adr_id', 'unknown')}"
    content = {
        "adr_id": adr.get("adr_id"), "title": adr.get("title"),
        "root_cause": f"a decision (swap {adr.get('from', {}).get('lang')}→"
                      f"{adr.get('to', {}).get('lang')}) built no dependency graph, so no control "
                      f"caught new/residual FROM artifacts",
        "graph_digest": graph.get("graph_digest"), "residual": graph.get("unported_count"),
        "wave1_ok": wave1.get("ok"), "wave2_plan_size": wave2.get("residual"),
        "rca_doc": rca_doc, "root_cause_graph_svg": svg,
    }
    content_digest = _digest(content)
    cite = f"commons:{domain}/{name}@{version}+{content_digest[:12]}"
    asset = {
        "commons_id": cite, "asset_type": "resolution", "domain": domain, "name": name,
        "version": version, "category": "dependency-swap-percolation",
        "tags": sorted({"rca", "resolution", "swap", "blast-radius", "self-healing",
                        adr.get("from", {}).get("lang", ""), adr.get("to", {}).get("lang", "")} - {""}),
        "content_digest": "sha256:" + content_digest,
        "reproducible": bool(graph.get("graph_digest")),  # carries the digest to rebuild the graph
        "recommendation": "when this failure class recurs, apply firewall_1 (adr_dependency_graph) "
                          "before authoring in scope; reuse this asset's remediation plan",
        "reuse_history": [], "feedback": [], "deposited_at": _now(),
        "content": content,
    }
    asset["receipt_digest"] = "sha256:" + _digest({k: v for k, v in asset.items()
                                                   if k not in ("receipt_digest",)})
    return asset


if __name__ == "__main__":
    import sys
    from pathlib import Path
    import adr_dependency_graph as adg

    adr = json.loads(Path("governance/adr/ADR-0001-nix-to-guix.json").read_text()) \
        if Path("governance/adr/ADR-0001-nix-to-guix.json").exists() \
        else json.loads(Path(sys.argv[1]).read_text())
    root = sys.argv[1] if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir() else str(Path.home() / "dev/source-os")
    graph = adg.build_dependency_graph(adr, root)
    w1 = adg.wave1_prevent(adr, ["packages/sourceos-shell/default.nix"], root=root)
    w2 = adg.wave2_detect_heal(adr, graph)
    svg = render_root_cause_svg(graph)
    asset = build_resolution_asset(adr=adr, graph=graph, wave1=w1, wave2=w2,
                                   rca_doc="docs/ADR_PERCOLATION.md", svg=svg)
    outdir = Path("artifacts/resolutions")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{asset['name']}.svg").write_text(svg)
    (outdir / f"{asset['name']}.json").write_text(
        json.dumps({**asset, "content": {**asset["content"], "root_cause_graph_svg": "<embedded.svg>"}},
                   indent=2, sort_keys=True))
    print(json.dumps({"commons_id": asset["commons_id"], "asset_type": asset["asset_type"],
                      "tags": asset["tags"], "residual": asset["content"]["residual"],
                      "svg_bytes": len(svg), "svg": str(outdir / f"{asset['name']}.svg")}, indent=2))
