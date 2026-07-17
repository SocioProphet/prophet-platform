"""Ontogenesis ontology access for the Studio — the REAL classes, not a mock.

Loads the vendored Ontogenesis class index (data/ontogenesis_index.json — generated from the real
~/dev/ontogenesis TTL corpus by tools/gen_ontogenesis_index.py: 817 classes, 621 object properties,
590 datatype properties). Provides class resolution + property lookup (with subClassOf inheritance) so
that ontology actions can be TYPED against genuine classes and their effects VALIDATED against the
class's declared properties/relations — instead of a free-text label that sets any property.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

_INDEX_PATH = os.path.join(os.path.dirname(__file__), "data", "ontogenesis_index.json")


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    try:
        with open(_INDEX_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"classes": [], "counts": {}, "base_iri": "", "commit": "missing"}


@lru_cache(maxsize=1)
def _by_iri() -> dict[str, dict[str, Any]]:
    return {c["iri"]: c for c in _index().get("classes", [])}


@lru_cache(maxsize=1)
def _by_label() -> dict[str, dict[str, Any]]:
    # last-writer-wins is fine; resolve() prefers an exact iri match first anyway
    return {str(c.get("label", "")).lower(): c for c in _index().get("classes", [])}


def all_classes() -> list[dict[str, Any]]:
    return _index().get("classes", [])


def base_iri() -> str:
    return _index().get("base_iri", "")


def counts() -> dict[str, Any]:
    return {**_index().get("counts", {}), "commit": _index().get("commit"), "parsed_files": _index().get("parsed_files")}


def resolve_class(name: str) -> dict[str, Any] | None:
    """Resolve a class by its curie (e.g. 'party:Party') or its label ('Party'), case-insensitively."""
    if not name:
        return None
    n = name.strip()
    return _by_iri().get(n) or _by_label().get(n.lower())


def class_properties(iri: str, _depth: int = 0) -> dict[str, dict[str, Any]]:
    """All properties declared on a class OR inherited from its subClassOf ancestors, keyed by property curie."""
    cls = _by_iri().get(iri)
    if not cls or _depth > 12:
        return {}
    out: dict[str, dict[str, Any]] = {p["iri"]: p for p in cls.get("properties", [])}
    for parent in cls.get("subClassOf", []):
        for k, v in class_properties(parent, _depth + 1).items():
            out.setdefault(k, v)
    return out


def _resolve_property(props: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Match a property by curie or by label (case-insensitive) among a class's (inherited) properties."""
    if name in props:
        return props[name]
    low = name.strip().lower()
    return next((p for p in props.values() if str(p.get("label", "")).lower() == low), None)


@lru_cache(maxsize=1)
def prefixes() -> dict[str, str]:
    return _index().get("prefixes", {})


def expand(curie: str) -> str:
    """Expand a curie (prefix:name) to a full IRI via the corpus prefix map; pass through full IRIs."""
    if not curie or "://" in curie:
        return curie
    if ":" in curie:
        p, _, name = curie.partition(":")
        ns = prefixes().get(p)
        if ns:
            return ns + name
    return curie


def property_on_class(class_iri: str, name: str) -> dict[str, Any] | None:
    """Resolve a property (by curie or label) among a class's declared/inherited properties."""
    return _resolve_property(class_properties(class_iri), name)


def validate_action(target_type: str, effects: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    """Type-check an action against the ontology. Returns (resolved_class, errors). The class must exist; each
    set_property effect's property must be a declared (or inherited) property of the class; each add_edge label
    must be a declared OBJECT property. set_status is allowed as a lifecycle convenience."""
    errors: list[str] = []
    cls = resolve_class(target_type)
    if not cls:
        return None, [f"target_type '{target_type}' is not an Ontogenesis class (see GET /api/studio/ontology)"]
    props = class_properties(cls["iri"])
    for i, e in enumerate(effects):
        op = e.get("op")
        if op == "set_property":
            prop = e.get("property") or ""
            match = _resolve_property(props, prop)
            if not match:
                errors.append(f"effect[{i}]: property '{prop}' is not declared on {cls['iri']} or its ancestors")
        elif op == "add_edge":
            lbl = e.get("label") or ""
            match = _resolve_property(props, lbl)
            if not match:
                errors.append(f"effect[{i}]: relation '{lbl}' is not a declared property of {cls['iri']}")
            elif match.get("kind") != "object":
                errors.append(f"effect[{i}]: '{lbl}' is a datatype property, not a relation (use set_property)")
        # set_status is a lifecycle convenience — always allowed
    return cls, errors
