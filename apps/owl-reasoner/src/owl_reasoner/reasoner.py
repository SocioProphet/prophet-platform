"""OWL/RDFS reasoner bridge — the missing inference over the estate's graph.

Recon found RDFS/OWL/SHACL inference living in Ontogenesis (rdflib/pyshacl) but NOT wired to HellGraph.
This is the bridge: it takes the graph as RDF (HellGraph's graph.ttl already emits KKO-typed Turtle),
computes the RDFS/OWL-RL deductive closure (the ENTAILMENTS — knowledge derivable but not stated), and
validates against SHACL shapes. That is Protégé/Stardog-class reasoning, made proof-carrying: every
entailed triple is a derivation over stated facts + the KKO upper ontology, not an assertion.

Pure (no HTTP) so it is trivially testable; the service wrapper + graph pull live in server.py.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
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

# The KKO upper ontology (KBpedia Knowledge Ontology), vendored as package data so it ships in the image.
_KKO_PATH = Path(__file__).resolve().parent / "data" / "kko-2.10.n3"


@lru_cache(maxsize=1)
def _kko_tbox() -> Graph:
    """The KKO TBox (168 classes / 167 rdfs:subClassOf), parsed once and cached. Returns an empty graph
    if the vendored file is missing, so ``with_kko`` degrades to a no-op rather than failing."""
    g = Graph()
    try:
        # the .n3 is Turtle-compatible; parse as turtle to avoid rdflib's noisy N3-parser deprecations.
        g.parse(_KKO_PATH.as_posix(), format="turtle")
    except Exception:  # pragma: no cover — missing/parse issue must never take reasoning down
        pass
    return g


def reason(turtle: str, shapes: str | None = None, inference: str = "rdfs",
           limit: int = 100, explain: bool = False, with_kko: bool = False) -> dict[str, Any]:
    """Compute entailments (+ optional SHACL validation) over a Turtle graph.

    inference: 'rdfs' | 'owlrl'/'owl2rl' | 'both' | 'none'. Returns input/entailed counts, a sample of the
    NEW (derived) triples, optional per-triple JUSTIFICATIONS (SOUND proof trees grounded in asserted facts,
    plus honest coverage — not the "why" incumbents' opaque reasoners hide), and, with shapes, the SHACL report.

    with_kko: merge the full KKO upper ontology (the vendored TBox) before closure, so data typed with
    kko: classes gets subClassOf transitivity + type propagation WITHOUT the caller inlining the axioms.
    """
    inference = _PROFILE_ALIASES.get(inference, inference)
    g = Graph()
    g.parse(data=turtle, format="turtle")
    kko_tbox_triples = 0
    if with_kko:
        tbox = _kko_tbox()
        for t in tbox:
            g.add(t)
        kko_tbox_triples = len(tbox)
    baseline = set(g)  # to diff out the entailments (the KKO TBox is baseline — never counted as entailed)
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
        "kko_tbox": {"loaded": with_kko, "triples": kko_tbox_triples},
        "profile": {"rdfs": "RDFS", "owlrl": "OWL 2 RL", "both": "OWL 2 RL + RDFS", "none": "none"}.get(mode, mode),
        # proof-carrying: each entailed triple is a derivation over stated facts + the ontology
        "entailments": [f"{_c(s)} {_c(p)} {_c(o)}" for (s, p, o) in entailed[:limit]],
    }
    if explain:
        # SOUND proof trees grounded in the ASSERTED baseline, with HONEST coverage. The old version cited
        # underived triples as premises and SILENTLY dropped whatever it couldn't explain (~93%); now every
        # premise is proven down to asserted facts, and unexplained entailments are COUNTED, not hidden.
        target = entailed[:limit]
        proofs = [pf for t in target if (pf := _prove(baseline, g, t, frozenset())) is not None and "rule" in pf]
        result["justifications"] = proofs
        result["justification_coverage"] = {
            "explained": len(proofs), "unexplained": len(target) - len(proofs), "of": len(target),
            "note": "unexplained entailments are OWL-RL axiomatic/tautological triples or rules outside the "
                    "RDFS/OWL-RL subset this prover covers (type propagation, subclass/subproperty transitivity, "
                    "domain/range, symmetric) — reported, never silently dropped",
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


Triple = tuple[Any, Any, Any]
_MAX_PROOF_DEPTH = 16


def _rule_candidates(g: Graph, s: Any, p: Any, o: Any):
    """Yield (rule_name, [premise_triples]) for EVERY applicable RDFS/OWL-RL rule that could derive (s,p,o).
    The prover tries each candidate and keeps the first whose premises all ground in asserted facts, so a
    branch that can't be grounded doesn't poison a conclusion that has another valid derivation."""
    if p == RDF.type:
        for c in g.objects(s, RDF.type):                       # rdfs9: s a C, C ⊑ o ⊢ s a o
            if c != o and (c, RDFS.subClassOf, o) in g:
                yield "rdfs9:type-propagation", [(s, RDF.type, c), (c, RDFS.subClassOf, o)]
        for pr, x in g.predicate_objects(s):                   # rdfs2: s P x, P domain o ⊢ s a o
            if isinstance(pr, URIRef) and (pr, RDFS.domain, o) in g:
                yield "rdfs2:domain", [(s, pr, x), (pr, RDFS.domain, o)]
        for x, pr in g.subject_predicates(s):                  # rdfs3: x P s, P range o ⊢ s a o
            if isinstance(pr, URIRef) and (pr, RDFS.range, o) in g:
                yield "rdfs3:range", [(x, pr, s), (pr, RDFS.range, o)]
    if p == RDFS.subClassOf:                                   # rdfs11: s ⊑ M, M ⊑ o ⊢ s ⊑ o
        for m in g.objects(s, RDFS.subClassOf):
            if m not in (s, o) and (m, RDFS.subClassOf, o) in g:
                yield "rdfs11:subClassOf-transitivity", [(s, RDFS.subClassOf, m), (m, RDFS.subClassOf, o)]
    if p == RDFS.subPropertyOf:                                # rdfs5: subPropertyOf transitivity
        for m in g.objects(s, RDFS.subPropertyOf):
            if m not in (s, o) and (m, RDFS.subPropertyOf, o) in g:
                yield "rdfs5:subPropertyOf-transitivity", [(s, RDFS.subPropertyOf, m), (m, RDFS.subPropertyOf, o)]
    if isinstance(p, URIRef) and p not in (RDF.type, RDFS.subClassOf, RDFS.subPropertyOf):
        for q in g.predicates(s, o):                           # rdfs7: s Q o, Q ⊑ p ⊢ s p o
            if q != p and isinstance(q, URIRef) and (q, RDFS.subPropertyOf, p) in g:
                yield "rdfs7:subPropertyOf", [(s, q, o), (q, RDFS.subPropertyOf, p)]
        if (p, RDF.type, OWL.SymmetricProperty) in g and (o, p, s) in g:  # owl symmetric
            yield "owl:SymmetricProperty", [(o, p, s), (p, RDF.type, OWL.SymmetricProperty)]


def _prove(baseline: set[Triple], g: Graph, triple: Triple, seen: frozenset[Triple], depth: int = 0) -> dict[str, Any] | None:
    """SOUND proof tree: ground `triple` in ASSERTED (baseline) facts via RDFS/OWL-RL rules, recursing on
    derived premises. Every leaf is an asserted triple — a premise can never be an unproven derived fact
    (the bug the old 1-ply version had: it checked the post-closure graph and cited underived triples)."""
    concl = f"{_c(triple[0])} {_c(triple[1])} {_c(triple[2])}"
    if triple in baseline:
        return {"conclusion": concl, "asserted": True}
    if depth >= _MAX_PROOF_DEPTH or triple in seen:
        return None
    seen = seen | {triple}
    for rule, premises in _rule_candidates(g, *triple):
        proofs = [_prove(baseline, g, prem, seen, depth + 1) for prem in premises]
        if all(pr is not None for pr in proofs):
            return {"conclusion": concl, "rule": rule, "premises": proofs}
    return None


def _c(term: Any) -> str:
    """Compact a term for display (last path/hash segment of an IRI; literals as-is)."""
    s = str(term)
    if s.startswith("http"):
        for sep in ("#", "/"):
            if sep in s:
                return s.rsplit(sep, 1)[-1]
    return s
