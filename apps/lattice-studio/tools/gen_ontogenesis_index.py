#!/usr/bin/env python3
"""Generate the vendored Ontogenesis class index for lattice-studio (dev-time).

Parses the real Ontogenesis TTL corpus (~/dev/ontogenesis) and emits a compact JSON index of classes +
their declared properties/relations, so the Studio serves REAL ontology classes (not the old 2-item mock)
and actions can be typed against them. Commit the output; it is a sovereign, versioned build artifact.

    python tools/gen_ontogenesis_index.py <path-to-ontogenesis> src/lattice_studio/data/ontogenesis_index.json
"""
import glob
import json
import os
import sys

import rdflib
from rdflib.namespace import OWL, RDF, RDFS


def curie(g: rdflib.Graph, uri) -> str:
    try:
        p, ns, name = g.compute_qname(uri, generate=False)
        return f"{p}:{name}" if p else str(name)
    except Exception:
        return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def label(g: rdflib.Graph, uri) -> str:
    lbl = g.value(uri, RDFS.label)
    return str(lbl) if lbl else curie(g, uri).split(":")[-1]


def main() -> None:
    root, out, commit = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "unknown")
    g = rdflib.Graph()
    parsed = 0
    for f in sorted(glob.glob(os.path.join(root, "**/*.ttl"), recursive=True)):
        try:
            g.parse(f, format="turtle"); parsed += 1
        except Exception:  # noqa: BLE001 — skip a malformed module, keep the corpus
            pass

    # properties grouped by their declared domain class
    props_by_domain: dict = {}
    for kind, ptype in (("object", OWL.ObjectProperty), ("datatype", OWL.DatatypeProperty)):
        for p in g.subjects(RDF.type, ptype):
            dom = g.value(p, RDFS.domain)
            rng = g.value(p, RDFS.range)
            entry = {"iri": curie(g, p), "label": label(g, p), "kind": kind,
                     "range": curie(g, rng) if rng else None}
            key = curie(g, dom) if dom else "(unscoped)"
            props_by_domain.setdefault(key, []).append(entry)

    classes = []
    for c in g.subjects(RDF.type, OWL.Class):
        if isinstance(c, rdflib.BNode):
            continue
        cc = curie(g, c)
        parents = [curie(g, s) for s in g.objects(c, RDFS.subClassOf) if not isinstance(s, rdflib.BNode)]
        classes.append({"iri": cc, "label": label(g, c), "subClassOf": sorted(parents),
                        "properties": sorted(props_by_domain.get(cc, []), key=lambda x: x["iri"])})
    classes.sort(key=lambda c: c["iri"])

    index = {
        "source": "ontogenesis", "commit": commit, "base_iri": "https://socioprophet.dev/ont/ontogenesis#",
        "parsed_files": parsed,
        # The prefix map is LOAD-BEARING: ontology.expand() needs it to turn curies into full IRIs.
        # Without it, SHACL writeback validation silently targets nothing (vacuous conforms=True).
        "prefixes": {p: str(ns) for p, ns in g.namespaces() if p and not p.startswith(("xml", "rdf", "rdfs", "owl", "xsd"))},
        "counts": {"classes": len(classes),
                   "object_properties": sum(1 for v in props_by_domain.values() for e in v if e["kind"] == "object"),
                   "datatype_properties": sum(1 for v in props_by_domain.values() for e in v if e["kind"] == "datatype")},
        "classes": classes,
    }
    with open(out, "w") as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"parsed {parsed} ttl → {len(classes)} classes, wrote {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
