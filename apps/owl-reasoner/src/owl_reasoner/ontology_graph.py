"""Ontology TBox → graph (WebVOWL-style) — so our 252 ontology files can actually be SEEN.

The KE audit's gap: we author ontologies as Turtle and can *reason* over them, but there is no way to
visualize the class/property structure (WebVOWL/VOWL do this for OWL out of the box). This extracts the
TBox as a graph a viewer renders: classes → nodes, rdfs:subClassOf + owl:ObjectProperty (domain→range)
→ edges. Pure rdflib; the frontend just draws the nodes/edges (reusing the estate's force-graph).
"""
from __future__ import annotations

from typing import Any

from rdflib import Graph, RDF, RDFS, OWL, URIRef


def _local(u: Any) -> str:
    s = str(u)
    for sep in ("#", "/"):
        if sep in s:
            return s.rsplit(sep, 1)[-1]
    return s


def tbox_graph(turtle: str, limit: int = 1000) -> dict[str, Any]:
    """Extract the TBox (classes + subClassOf + object-property domain→range) as a renderable graph."""
    g = Graph()
    g.parse(data=turtle, format="turtle")

    def label(u: Any) -> str:
        lbl = g.value(u, RDFS.label)
        return str(lbl) if lbl else _local(u)

    classes: set[Any] = set()
    for s in g.subjects(RDF.type, OWL.Class):
        classes.add(s)
    for s in g.subjects(RDF.type, RDFS.Class):
        classes.add(s)
    for s, _, o in g.triples((None, RDFS.subClassOf, None)):
        classes.add(s)
        if isinstance(o, URIRef):
            classes.add(o)
    classes = {c for c in classes if isinstance(c, URIRef)}

    nodes = [{"id": str(c), "label": label(c), "type": "class"} for c in classes]

    edges: list[dict[str, Any]] = []
    for s, _, o in g.triples((None, RDFS.subClassOf, None)):
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            edges.append({"source": str(s), "target": str(o), "label": "subClassOf", "type": "subClassOf"})
    for p in g.subjects(RDF.type, OWL.ObjectProperty):
        dom = g.value(p, RDFS.domain)
        rng = g.value(p, RDFS.range)
        if isinstance(dom, URIRef) and isinstance(rng, URIRef):
            edges.append({"source": str(dom), "target": str(rng), "label": label(p), "type": "objectProperty"})

    return {
        "nodes": nodes[:limit],
        "edges": edges[:limit],
        "counts": {"classes": len(nodes), "subclass_edges": sum(1 for e in edges if e["type"] == "subClassOf"),
                   "object_properties": sum(1 for e in edges if e["type"] == "objectProperty")},
    }
