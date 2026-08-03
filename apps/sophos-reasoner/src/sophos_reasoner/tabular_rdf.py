"""Tabular → RDF mapping (R2RML-style) — the data-integration on-ramp we had zero of.

The recurring enterprise ask "turn my table/CSV into the graph" (Ontop/eccenca/Stardog sell it as OBDA).
This is the mapping CORE of that: an R2RML-subset that turns rows into RDF via a declarative map —
a subject template, an optional class, and column→predicate assignments (literal or IRI-templated object).
It MATERIALIZES (vs OBDA's live-DB virtualization), which is the honest, dependency-light first step: no
DB driver, pure rdflib, trivially testable. Reuses the estate's Turtle/JSON-LD serialization so mapped
data is immediately queryable + dereferenceable alongside authored ontologies.

  map = {
    "base": "http://ex/",
    "subject_template": "person/{id}",          # {col} substituted from each row
    "class": "Person",                            # optional rdf:type (relative to base or absolute IRI)
    "predicates": {"full_name": "foaf:name"},     # column → predicate (CURIE or IRI); literal object
    "object_iri": {"employer": "org/{employer}"}, # column → IRI-templated object (a reference, not a literal)
    "prefixes": {"foaf": "http://xmlns.com/foaf/0.1/"}
  }
"""
from __future__ import annotations

import re
from typing import Any

from rdflib import RDF, Graph, Literal, Namespace, URIRef

_TEMPLATE = re.compile(r"\{([^}]+)\}")


def _fill(template: str, row: dict[str, Any]) -> str | None:
    """Substitute {col} placeholders from the row; None if any referenced column is missing/empty."""
    missing = False

    def sub(m: re.Match[str]) -> str:
        nonlocal missing
        v = row.get(m.group(1))
        if v is None or v == "":
            missing = True
            return ""
        return str(v)

    out = _TEMPLATE.sub(sub, template)
    return None if missing else out


def _resolve(term: str, base: str, prefixes: dict[str, str]) -> URIRef:
    """A CURIE (pfx:local), an absolute IRI (has scheme), or a base-relative term → a full IRI."""
    if term.startswith("http://") or term.startswith("https://") or term.startswith("urn:"):
        return URIRef(term)
    if ":" in term:
        pfx, local = term.split(":", 1)
        if pfx in prefixes:
            return URIRef(prefixes[pfx] + local)
    return URIRef(base + term)


def map_rows(rows: list[dict[str, Any]], mapping: dict[str, Any]) -> dict[str, Any]:
    """Apply an R2RML-style mapping to rows → an RDF graph, returned as Turtle + JSON-LD + counts."""
    base = mapping.get("base", "http://sovereign.local/")
    prefixes: dict[str, str] = dict(mapping.get("prefixes", {}))
    subj_tpl = mapping.get("subject_template")
    if not subj_tpl:
        raise ValueError("mapping.subject_template is required")
    cls = mapping.get("class")
    preds: dict[str, str] = mapping.get("predicates", {})
    obj_iri: dict[str, str] = mapping.get("object_iri", {})

    g = Graph()
    for pfx, ns in prefixes.items():
        g.bind(pfx, Namespace(ns))

    mapped = 0
    skipped = 0
    for row in rows:
        subj_local = _fill(subj_tpl, row)
        if subj_local is None:
            skipped += 1   # row lacks the key(s) needed to mint a subject → cannot map it
            continue
        subj = _resolve(subj_local, base, prefixes)
        mapped += 1
        if cls:
            g.add((subj, RDF.type, _resolve(cls, base, prefixes)))
        for col, pred in preds.items():
            val = row.get(col)
            if val is None or val == "":
                continue
            g.add((subj, _resolve(pred, base, prefixes), Literal(val)))
        for col, tpl in obj_iri.items():
            filled = _fill(tpl, row)
            if filled is None:
                continue
            # the predicate for an IRI object is the column's declared predicate, else a base-relative term
            pred = preds.get(col, col)
            g.add((subj, _resolve(pred, base, prefixes), _resolve(filled, base, prefixes)))

    return {
        "rows_in": len(rows),
        "mapped": mapped,
        "skipped": skipped,
        "triples": len(g),
        "turtle": g.serialize(format="turtle"),
        "jsonld": g.serialize(format="json-ld"),
    }
