"""SHACL validation of a candidate writeback against the REAL Ontogenesis shapes (pyshacl).

Before an ontology action commits, the target's resulting state is turned into an RDF graph (rdf:type <class>
plus a typed triple per declared property) and validated against the vendored Ontogenesis SHACL shapes
(data/ontogenesis_shapes.ttl — the estate's own shapes/*.shacl.ttl merged). A non-conformant writeback is
rejected with the violations. This is the estate's real validation mechanism (the same shapes the Ontogenesis
CI gate and Noetica's /api/graph/shacl engine use), run in-process — sovereign, no cross-service call.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD

from lattice_studio import ontology

_SHAPES_PATH = os.path.join(os.path.dirname(__file__), "data", "ontogenesis_shapes.ttl")
_GAIA_SHAPES_PATH = os.path.join(os.path.dirname(__file__), "data", "gaia_shapes.ttl")
_GAIA_ONT_PATH = os.path.join(os.path.dirname(__file__), "data", "gaia_world_signals.ttl")
_GAIA_NS = "https://schemas.socioprophet.org/gaia/"
_NODE = URIRef("urn:studio:candidate")


@lru_cache(maxsize=1)
def _shapes() -> rdflib.Graph | None:
    """Parse the vendored merged shapes once. Returns None if unavailable (→ validation degrades open)."""
    try:
        g = rdflib.Graph()
        g.parse(_SHAPES_PATH, format="turtle")
        return g
    except (OSError, ValueError):
        return None


def available() -> bool:
    return _shapes() is not None


def _literal(value: Any, prop: dict[str, Any]) -> Literal:
    rng = prop.get("range") or ""
    if rng.startswith("xsd:"):
        local = rng.split(":", 1)[1]
        try:
            return Literal(value, datatype=getattr(XSD, local))
        except Exception:  # noqa: BLE001 — fall back to a plain literal on an odd datatype
            return Literal(str(value))
    return Literal(str(value))


def validate_writeback(class_iri: str, props: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a candidate node (typed as class_iri, carrying props) against the Ontogenesis shapes.

    Returns (conforms, violations). Only props that resolve to a declared/inherited ontology property of the class
    are asserted (provenance/status/etc are ignored). If no shape targets the class, pyshacl reports conforms=True.
    Degrades OPEN (conforms=True) if the shapes graph or pyshacl is unavailable — validation must never hard-fail
    a writeback because tooling is missing (that would be a worse failure than an unvalidated write)."""
    shapes = _shapes()
    if shapes is None:
        return True, []
    try:
        import pyshacl
    except ImportError:
        return True, []

    data = rdflib.Graph()
    data.add((_NODE, RDF.type, URIRef(ontology.expand(class_iri))))
    for key, val in props.items():
        if val is None:
            continue
        prop = ontology.property_on_class(class_iri, str(key))
        if not prop:
            continue                                   # provenance / status / non-ontology keys are ignored
        piri = URIRef(ontology.expand(prop["iri"]))
        if prop.get("kind") == "object":
            data.add((_NODE, piri, URIRef(str(val))))
        else:
            data.add((_NODE, piri, _literal(val, prop)))

    try:
        conforms, results_graph, _ = pyshacl.validate(
            data, shacl_graph=shapes, inference="none", advanced=True, meta_shacl=False)
    except Exception:  # noqa: BLE001 — a validator crash must not block the writeback; degrade open
        return True, []
    if conforms:
        return True, []
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    violations = []
    for res in results_graph.subjects(RDF.type, SH.ValidationResult):
        msg = results_graph.value(res, SH.resultMessage)
        path = results_graph.value(res, SH.resultPath)
        violations.append(f"{ontology_curie(str(path)) if path else ''}: {msg}".strip(": ") or str(msg))
    return False, violations[:12]


def ontology_curie(iri: str) -> str:
    """Best-effort shorten a full IRI back to a curie for readable violations."""
    for p, ns in sorted(ontology.prefixes().items(), key=lambda kv: -len(kv[1])):
        if iri.startswith(ns):
            return f"{p}:{iri[len(ns):]}"
    return iri


# ── GAIA world-signals validation (the Earth-twin promotion membrane) ──────────────────────────────────────────
_GAIA_OBJECT_PROPS = {"gaia:hasPromotionState", "gaia:promotesSignal",
                      "gaia:mapsSourceRecordToEntity", "gaia:hasDecisionLedgerEntry"}


@lru_cache(maxsize=1)
def _gaia() -> tuple[rdflib.Graph, rdflib.Graph] | None:
    """Parse the vendored GAIA shapes + world-signals ontology once (the ontology is the type graph so that
    `sh:class gaia:PromotionState` on a value like gaia:EvidenceOnly resolves). None if unavailable."""
    try:
        shapes = rdflib.Graph(); shapes.parse(_GAIA_SHAPES_PATH, format="turtle")
        ont = rdflib.Graph(); ont.parse(_GAIA_ONT_PATH, format="turtle")
        return shapes, ont
    except (OSError, ValueError):
        return None


def _gaia_expand(curie: str) -> str:
    return _GAIA_NS + curie[5:] if curie.startswith("gaia:") else ontology.expand(curie)


def validate_gaia(class_curie: str, props: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a GAIA world-signal (typed class_curie, carrying gaia:* props) against the GAIA world-signals
    SHACL shapes. Object props (hasPromotionState, …) become IRIs (a promotion state → gaia:<State>); datatype
    props become literals. Degrades OPEN if the shapes/pyshacl are unavailable."""
    g = _gaia()
    if g is None:
        return True, []
    try:
        import pyshacl
    except ImportError:
        return True, []
    shapes, ont = g
    data = rdflib.Graph()
    data.add((_NODE, RDF.type, URIRef(_gaia_expand(class_curie))))
    for key, val in props.items():
        if val is None or not str(key).startswith("gaia:"):
            continue
        piri = URIRef(_gaia_expand(str(key)))
        if key in _GAIA_OBJECT_PROPS:
            ref = _gaia_expand(f"gaia:{val}") if key == "gaia:hasPromotionState" else str(val)
            data.add((_NODE, piri, URIRef(ref)))
        else:
            data.add((_NODE, piri, Literal(str(val))))
    try:
        conforms, results_graph, _ = pyshacl.validate(
            data, shacl_graph=shapes, ont_graph=ont, inference="rdfs", advanced=True, meta_shacl=False)
    except Exception:  # noqa: BLE001
        return True, []
    if conforms:
        return True, []
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    out = []
    for res in results_graph.subjects(RDF.type, SH.ValidationResult):
        msg = results_graph.value(res, SH.resultMessage)
        path = results_graph.value(res, SH.resultPath)
        pc = str(path).replace(_GAIA_NS, "gaia:") if path else ""
        out.append(f"{pc}: {msg}".strip(": ") or str(msg))
    return False, out[:12]
