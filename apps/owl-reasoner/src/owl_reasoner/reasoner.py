"""OWL/RDFS reasoner bridge — the missing inference over the estate's graph.

Recon found RDFS/OWL/SHACL inference living in Ontogenesis (rdflib/pyshacl) but NOT wired to HellGraph.
This is the bridge: it takes the graph as RDF (HellGraph's graph.ttl already emits KKO-typed Turtle),
computes the RDFS/OWL-RL deductive closure (the ENTAILMENTS — knowledge derivable but not stated), and
validates against SHACL shapes. That is Protégé/Stardog-class reasoning, made proof-carrying: every
entailed triple is a derivation over stated facts + the KKO upper ontology, not an assertion.

Pure (no HTTP) so it is trivially testable; the service wrapper + graph pull live in server.py.
"""
from __future__ import annotations

from typing import Any

from rdflib import Graph

try:
    from owlrl import DeductiveClosure, RDFS_Semantics, OWLRL_Semantics
    _HAVE_OWLRL = True
except Exception:  # pragma: no cover
    _HAVE_OWLRL = False

try:
    import pyshacl
    _HAVE_SHACL = True
except Exception:  # pragma: no cover
    _HAVE_SHACL = False


def reason(turtle: str, shapes: str | None = None, inference: str = "rdfs", limit: int = 100) -> dict[str, Any]:
    """Compute entailments (+ optional SHACL validation) over a Turtle graph.

    inference: 'rdfs' | 'owlrl' | 'both' | 'none'. Returns the input/entailed counts, a sample of the
    NEW (derived) triples, and — when shapes are supplied — the SHACL conformance report.
    """
    g = Graph()
    g.parse(data=turtle, format="turtle")
    baseline = set(g)  # to diff out the entailments
    n_in = len(baseline)

    mode = inference if _HAVE_OWLRL else "unavailable"
    if inference != "none" and _HAVE_OWLRL:
        if inference == "owlrl":
            DeductiveClosure(OWLRL_Semantics).expand(g)
        elif inference == "both":
            DeductiveClosure(OWLRL_Semantics, rdfs_closure=True).expand(g)
        else:  # 'rdfs' (default)
            DeductiveClosure(RDFS_Semantics).expand(g)

    entailed = [t for t in g if t not in baseline]
    result: dict[str, Any] = {
        "input_triples": n_in,
        "entailed_triples": len(entailed),
        "inference": mode,
        # proof-carrying: each entailed triple is a derivation over stated facts + the ontology
        "entailments": [f"{_c(s)} {_c(p)} {_c(o)}" for (s, p, o) in entailed[:limit]],
    }

    if shapes is not None:
        if not _HAVE_SHACL:
            result["shacl"] = {"available": False}
        else:
            sg = Graph()
            sg.parse(data=shapes, format="turtle")
            conforms, _report_graph, report_text = pyshacl.validate(g, shacl_graph=sg, inference="none", advanced=True)
            result["shacl"] = {"available": True, "conforms": bool(conforms), "report": report_text[:4000]}
    return result


def _c(term: Any) -> str:
    """Compact a term for display (last path/hash segment of an IRI; literals as-is)."""
    s = str(term)
    if s.startswith("http"):
        for sep in ("#", "/"):
            if sep in s:
                return s.rsplit(sep, 1)[-1]
    return s
