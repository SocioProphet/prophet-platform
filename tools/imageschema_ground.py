#!/usr/bin/env python3
"""Ground natural language onto image schemas via the ImageSchemaNet cartridge.

The cartridge (apps/hellgraph-service/ontology/imageschemanet.ttl) is an estate-authored,
KKO-alignable seed of the image-schema taxonomy and the `:activates` grounding model
(after De Giorgis, Gangemi & Gromann 2022, CC-BY 4.0). This tool turns it into a callable
grounding function: a lexical unit or a sentence -> the image schema(s) it activates.

Two modes, both fail-closed (a control that certifies nothing is worthless):
  --verify   structural conformance of the cartridge (every image schema has core spatial
             primitives; every lexical activator activates a known image schema). For CI.
  --selftest golden lexical/sentence groundings must resolve to the expected schemas.

Run with no mode (or `make imageschemanet-grounding-check`) to do both. Proven able to go
red by tools/tests/test_imageschema_ground.py.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
CARTRIDGE = ROOT / "apps/hellgraph-service/ontology/imageschemanet.ttl"
ISN = Namespace("https://ontology.socioprophet.ai/imageschemanet#")


def load(path: Path = CARTRIDGE) -> Graph:
    g = Graph()
    g.parse(str(path), format="turtle")
    return g


def _activation_predicates(g: Graph) -> set[URIRef]:
    preds = {ISN.activates}
    preds.update(p for p, _, _ in g.triples((None, RDFS.subPropertyOf, ISN.activates)))
    return preds


def image_schemas(g: Graph) -> set[URIRef]:
    return set(g.subjects(RDFS.subClassOf, ISN.ImageSchema))


def _label(g: Graph, node: URIRef) -> str:
    lab = g.value(node, RDFS.label)
    return str(lab) if lab is not None else str(node).split("#")[-1]


def ground_lemma(g: Graph, lemma: str) -> set[str]:
    """Image-schema labels a single lemma activates (case-insensitive)."""
    preds = _activation_predicates(g)
    schemas = image_schemas(g)
    lemma = lemma.strip().lower()
    out: set[str] = set()
    for activator, _, lab in g.triples((None, RDFS.label, None)):
        if (activator, RDF.type, ISN.LexicalActivator) not in g:
            continue
        if str(lab).strip().lower() != lemma:
            continue
        for p in preds:
            for schema in g.objects(activator, p):
                if schema in schemas:
                    out.add(_label(g, schema))
    return out


def _lemma_candidates(token: str) -> set[str]:
    """A surface token plus a few conservative de-inflections, so real inflected text
    ('supports', 'entered', 'blocks') grounds against base-form activators. This is a
    lightweight stemmer, not a full lemmatiser — the seed's honest reach."""
    c = {token}
    if len(token) > 4 and token.endswith("ies"):
        c.add(token[:-3] + "y")            # carries -> carry
    if len(token) > 3 and token.endswith("es"):
        c.add(token[:-2])                  # encloses -> enclose
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        c.add(token[:-1])                  # supports -> support
    if len(token) > 5 and token.endswith("ing"):
        c.add(token[:-3]); c.add(token[:-3] + "e")  # blocking -> block / enclosing -> enclose
    if len(token) > 4 and token.endswith("ed"):
        c.add(token[:-2]); c.add(token[:-1])        # blocked -> block / arrived -> arrive
    return c


def ground_text(g: Graph, text: str) -> dict[str, set[str]]:
    """Annotate a sentence: {token: {image schemas}} for every token that activates one."""
    out: dict[str, set[str]] = {}
    for token in re.findall(r"[A-Za-z]+", text.lower()):
        schemas: set[str] = set()
        for cand in _lemma_candidates(token):
            schemas |= ground_lemma(g, cand)
        if schemas:
            out[token] = schemas
    return out


def verify(g: Graph) -> list[str]:
    """Structural conformance — fail-closed. Every image schema must declare its core
    spatial primitives; every lexical activator must activate a known image schema."""
    out: list[str] = []
    schemas = image_schemas(g)
    if not schemas:
        return ["cartridge declares no image schemas (rdfs:subClassOf isn:ImageSchema)"]
    for s in schemas:
        if not list(g.objects(s, ISN.hasCoreSP)):
            out.append(f"image schema {_label(g, s)} declares no core spatial primitives (isn:hasCoreSP)")
    preds = _activation_predicates(g)
    for activator in g.subjects(RDF.type, ISN.LexicalActivator):
        if g.value(activator, RDFS.label) is None:
            out.append(f"lexical activator {activator} has no rdfs:label")
        targets = {t for p in preds for t in g.objects(activator, p)}
        if not (targets & schemas):
            out.append(f"lexical activator {_label(g, activator)} activates no known image schema")
    return out


# Golden groundings — the paper's canonical examples + seed coverage. A miss here means the
# grounding regressed (or the cartridge lost an activation).
_GOLDEN: list[tuple[str, str]] = [
    ("contain", "CONTAINMENT"),
    ("inside", "CONTAINMENT"),
    ("The Obama administration entered into an agreement with Iran", "SOURCE_PATH_GOAL"),
    ("journey", "SOURCE_PATH_GOAL"),
    ("the shelf supports the book", "SUPPORT"),
    ("a barrier that blocks the road", "BLOCKAGE"),
    ("the periphery depends on the center", "CENTER_PERIPHERY"),
    ("every part of the whole", "PART_WHOLE"),
]


def selftest(g: Graph) -> list[str]:
    out: list[str] = []
    for text, expected in _GOLDEN:
        found = set().union(*ground_text(g, text).values()) if ground_text(g, text) else set()
        if expected not in found:
            out.append(f"grounding {text!r} -> {sorted(found) or 'nothing'}, expected {expected}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ImageSchemaNet grounding")
    ap.add_argument("--cartridge", default=str(CARTRIDGE), type=Path)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ground", metavar="TEXT", help="annotate a sentence with image schemas")
    args = ap.parse_args(argv)
    g = load(Path(args.cartridge))

    if args.ground:
        for lemma, schemas in ground_text(g, args.ground).items():
            print(f"  {lemma} -> {', '.join(sorted(schemas))}")
        return 0

    run_all = not (args.verify or args.selftest)
    violations: list[str] = []
    if args.verify or run_all:
        violations += verify(g)
    if args.selftest or run_all:
        violations += selftest(g)
    if violations:
        print("imageschemanet-grounding-check: FAIL")
        for v in violations:
            print(f"  - {v}")
        return 1
    n_schemas = len(image_schemas(g))
    n_act = len(set(g.subjects(RDF.type, ISN.LexicalActivator)))
    print(f"imageschemanet-grounding-check: OK — {n_schemas} image schemas, {n_act} lexical activators; golden groundings resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
