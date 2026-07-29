"""OWL/RDFS reasoner bridge — the missing inference over the estate's graph.

Recon found RDFS/OWL/SHACL inference living in Ontogenesis (rdflib/pyshacl) but NOT wired to HellGraph.
This is the bridge: it takes the graph as RDF (HellGraph's graph.ttl already emits KKO-typed Turtle),
computes the RDFS/OWL-RL deductive closure (the ENTAILMENTS — knowledge derivable but not stated), and
validates against SHACL shapes. That is Protégé/Stardog-class reasoning, made proof-carrying: every
entailed triple is a derivation over stated facts + the KKO upper ontology, not an assertion.

Pure (no HTTP) so it is trivially testable; the service wrapper + graph pull live in server.py.

VENDORED KKO TBox — provenance and integrity (see data/PROVENANCE.md):
    repo    SocioProphet/kbpedia @ 3f888b397255b69d1439fd95823e97011ed9440b (fork of KBpedia/kbpedia)
    path    versions/2.10/kko-demo.n3
    sha256  d907919fb40f20ed39a7fde0e8d114027449d9354a1976ce8248db5634cb7b07  (327,797 bytes)
    licence CC-BY-4.0 — (c) Michael K. Bergman & Fred Giasson (Cognonto / KBpedia)
The sha256 is ASSERTED AT IMPORT (nugget-extractor contract.py precedent). This copy is the
THIRD in the estate — the HellGraph engine vendors the same bytes at ontology/kko/kko-2.10.n3,
and hellgraph-sprint carries a checkout of it — so "byte-identical" was previously true only by
luck. KKO_SHA256 is the shared constant that makes it true BY ASSERTION: all copies pin the same
digest, so a drift in any one of them is caught where it is loaded rather than discovered as a
changed answer. A drifted TBox does not fail — it silently reclassifies, which is worse.
"""
from __future__ import annotations

import hashlib
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

# The pinned digest of the vendored TBox. Shared, byte-for-byte, with the HellGraph engine's copy
# (hellgraph ontology/kko/PROVENANCE.md) — that is the whole point: one constant, three copies.
KKO_SHA256 = "d907919fb40f20ed39a7fde0e8d114027449d9354a1976ce8248db5634cb7b07"
KKO_SOURCE = ("SocioProphet/kbpedia@3f888b397255b69d1439fd95823e97011ed9440b"
              " versions/2.10/kko-demo.n3 (CC-BY-4.0)")


def kko_file_digest(path: Path | None = None) -> str | None:
    """sha256 of a vendored KKO TBox file, or None when the file is absent.

    Separated from the import-time assertion so the integrity rule is exercisable against an
    arbitrary path in tests — the gate itself stays at import, where it cannot be skipped.
    """
    p = _KKO_PATH if path is None else path
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def verify_kko_integrity(path: Path | None = None) -> str:
    """Fail-closed integrity gate for the vendored TBox. Returns 'verified' or 'absent'.

    Raises RuntimeError when the file is PRESENT but its bytes are not the pinned ones. The two
    failure modes are deliberately NOT treated alike:

      absent   — a packaging condition this module has always degraded on (pyproject's
                 package-data rule exists precisely because an absent TBox once made `with_kko`
                 a silent no-op). It stays a degradation, and stays VISIBLE via
                 kko_tbox_status()'s unavailable_reason.
      drifted  — a supply-chain event. Reasoning over an ontology that is not the one we
                 declare does not fail, it returns DIFFERENT ENTAILMENTS, and every downstream
                 consumer of those entailments inherits the drift silently. There is no honest
                 degraded mode for "wrong axioms", so this is loud and terminal at import.
    """
    actual = kko_file_digest(path)
    if actual is None:
        return "absent"
    if actual != KKO_SHA256:
        p = _KKO_PATH if path is None else path
        raise RuntimeError(
            f"vendored KKO TBox drifted: sha256 {actual} != pinned {KKO_SHA256} ({p}); "
            f"re-vendor from {KKO_SOURCE} and update data/PROVENANCE.md. Refusing to reason "
            "over an ontology that is not the one this service declares.")
    return "verified"


# THE GATE. Asserted at import, not merely recorded in PROVENANCE.md — a provenance file that
# nothing verifies is decoration.
KKO_INTEGRITY = verify_kko_integrity()


@lru_cache(maxsize=1)
def _kko_tbox() -> Graph:
    """The KKO TBox (168 classes / 167 rdfs:subClassOf), parsed once and cached. Returns an empty graph
    if the vendored file is missing, so ``with_kko`` degrades to a no-op rather than failing.

    The bytes are already digest-verified at import (KKO_INTEGRITY), so anything parsed here is
    provably the declared ontology; only the absent case can reach the empty-graph path."""
    g = Graph()
    if KKO_INTEGRITY != "verified":  # pragma: no cover — absent package data
        return g
    try:
        # the .n3 is Turtle-compatible; parse as turtle to avoid rdflib's noisy N3-parser deprecations.
        g.parse(_KKO_PATH.as_posix(), format="turtle")
    except Exception:  # pragma: no cover — a parse issue must never take reasoning down
        pass
    return g


def kko_tbox_status(requested: bool, triples: int) -> dict[str, Any]:
    """What the KKO TBox actually did on this call, as opposed to what was asked for.

    Requested and loaded are separate facts. _kko_tbox() deliberately degrades rather than
    raising — a missing or unparseable vendored file must not take reasoning down — but that
    degradation has to be visible in the response, or `with_kko=true` reports success on a
    deployment where the ontology contributed nothing. `unavailable_reason` is present only
    when the two disagree, so a client never has to infer the difference from a zero.

    When the TBox IS loaded the response also carries the digest it was loaded under, so a
    caller can bind an entailment set to the exact ontology bytes that produced it.
    """
    loaded = requested and triples > 0
    status: dict[str, Any] = {"requested": requested, "loaded": loaded, "triples": triples}
    if loaded:
        status["sha256"] = KKO_SHA256
        status["source"] = KKO_SOURCE
    if requested and not loaded:
        status["unavailable_reason"] = (
            f"KKO TBox requested but no triples were parsed from {_KKO_PATH.name} "
            f"(vendored-artifact integrity: {KKO_INTEGRITY}); with_kko had no effect on this result"
        )
    return status


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
        # `loaded` used to be `with_kko` — the caller's REQUEST, not the outcome. _kko_tbox()
        # swallows a missing or unparseable file and returns an empty graph, so a deployment
        # without the TBox answered {"loaded": true, "triples": 0}: the response asserted the
        # ontology was in play while with_kko was silently a no-op.
        "kko_tbox": kko_tbox_status(with_kko, kko_tbox_triples),
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
