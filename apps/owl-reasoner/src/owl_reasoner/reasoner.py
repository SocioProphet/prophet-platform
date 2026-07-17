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

from rdflib import OWL, RDF, RDFS, Graph
from rdflib.term import URIRef

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


# OWL2-RL is the profile owlrl's OWLRL_Semantics implements — expose the standard profile name as an alias.
_PROFILE_ALIASES = {"owl2rl": "owlrl", "owl2-rl": "owlrl", "owl": "owlrl"}


def reason(turtle: str, shapes: str | None = None, inference: str = "rdfs",
           limit: int = 100, explain: bool = False) -> dict[str, Any]:
    """Compute entailments (+ optional SHACL validation) over a Turtle graph.

    inference: 'rdfs' | 'owlrl'/'owl2rl' | 'both' | 'none'. Returns input/entailed counts, a sample of the
    NEW (derived) triples, optional per-triple JUSTIFICATIONS (a 1-step derivation trace: rule + premises —
    the "why" incumbents' opaque reasoners don't emit), and, when shapes are supplied, the SHACL report.
    """
    inference = _PROFILE_ALIASES.get(inference, inference)
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
        "profile": {"rdfs": "RDFS", "owlrl": "OWL 2 RL", "both": "OWL 2 RL + RDFS", "none": "none"}.get(mode, mode),
        # proof-carrying: each entailed triple is a derivation over stated facts + the ontology
        "entailments": [f"{_c(s)} {_c(p)} {_c(o)}" for (s, p, o) in entailed[:limit]],
    }
    if explain:
        # Justification = a 1-step derivation trace grounding each entailment in premises the graph holds.
        result["justifications"] = [j for t in entailed[:limit] if (j := _justify(g, *t)) is not None]

    if shapes is not None:
        if not _HAVE_SHACL:
            result["shacl"] = {"available": False}
        else:
            sg = Graph()
            sg.parse(data=shapes, format="turtle")
            conforms, _report_graph, report_text = pyshacl.validate(g, shacl_graph=sg, inference="none", advanced=True)
            result["shacl"] = {"available": True, "conforms": bool(conforms), "report": report_text[:4000]}
    return result


def _justify(g: Graph, s: Any, p: Any, o: Any) -> dict[str, Any] | None:
    """Find a 1-step justification for an entailed triple: the rule that derives it + the premises the
    graph holds. Covers the load-bearing RDFS/OWL-RL rules (type propagation, subclass/subproperty
    transitivity, domain/range). Returns {conclusion, rule, premises[]} or None if not attributable."""
    def has(a: Any, b: Any, c: Any) -> bool:
        return (a, b, c) in g

    def prem(a: Any, b: Any, c: Any) -> str:
        return f"{_c(a)} {_c(b)} {_c(c)}"

    concl = f"{_c(s)} {_c(p)} {_c(o)}"

    if p == RDF.type:
        # type propagation: s a C , C ⊑ o  ⊢  s a o
        for c in g.objects(s, RDF.type):
            if c != o and has(c, RDFS.subClassOf, o):
                return {"conclusion": concl, "rule": "rdfs9:type-propagation",
                        "premises": [prem(s, RDF.type, c), prem(c, RDFS.subClassOf, o)]}
        # domain: s P x , P domain o  ⊢  s a o
        for pr, x in g.predicate_objects(s):
            if isinstance(pr, URIRef) and has(pr, RDFS.domain, o):
                return {"conclusion": concl, "rule": "rdfs2:domain",
                        "premises": [prem(s, pr, x), prem(pr, RDFS.domain, o)]}
        # range: x P s , P range o  ⊢  s a o
        for x, pr in g.subject_predicates(s):
            if isinstance(pr, URIRef) and has(pr, RDFS.range, o):
                return {"conclusion": concl, "rule": "rdfs3:range",
                        "premises": [prem(x, pr, s), prem(pr, RDFS.range, o)]}

    if p == RDFS.subClassOf:
        # subclass transitivity: s ⊑ M , M ⊑ o  ⊢  s ⊑ o
        for m in g.objects(s, RDFS.subClassOf):
            if m not in (s, o) and has(m, RDFS.subClassOf, o):
                return {"conclusion": concl, "rule": "rdfs11:subClassOf-transitivity",
                        "premises": [prem(s, RDFS.subClassOf, m), prem(m, RDFS.subClassOf, o)]}

    if p == RDFS.subPropertyOf:
        for m in g.objects(s, RDFS.subPropertyOf):
            if m not in (s, o) and has(m, RDFS.subPropertyOf, o):
                return {"conclusion": concl, "rule": "rdfs5:subPropertyOf-transitivity",
                        "premises": [prem(s, RDFS.subPropertyOf, m), prem(m, RDFS.subPropertyOf, o)]}

    if isinstance(p, URIRef) and p not in (RDF.type, RDFS.subClassOf, RDFS.subPropertyOf):
        # subproperty entailment: s Q o , Q ⊑ p  ⊢  s p o
        for q in g.predicates(s, o):
            if q != p and isinstance(q, URIRef) and has(q, RDFS.subPropertyOf, p):
                return {"conclusion": concl, "rule": "rdfs7:subPropertyOf",
                        "premises": [prem(s, q, o), prem(q, RDFS.subPropertyOf, p)]}
        # symmetric / inverse (OWL): s' P o with P owl:inverseOf p, or symmetric
        if has(p, RDF.type, OWL.SymmetricProperty) and has(o, p, s):
            return {"conclusion": concl, "rule": "owl:SymmetricProperty",
                    "premises": [prem(o, p, s), prem(p, RDF.type, OWL.SymmetricProperty)]}

    return None


def _c(term: Any) -> str:
    """Compact a term for display (last path/hash segment of an IRI; literals as-is)."""
    s = str(term)
    if s.startswith("http"):
        for sep in ("#", "/"):
            if sep in s:
                return s.rsplit(sep, 1)[-1]
    return s
