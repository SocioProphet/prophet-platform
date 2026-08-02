"""Teeth for ImageSchemaNet grounding (P1).

Golden groundings resolve; the shipped cartridge is structurally conformant; and a
broken cartridge (an activator pointing at no image schema, or a missing activation)
goes red — a grounding check that can't fail proves nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("rdflib")  # this suite owns its dep via `make imageschemanet-grounding-check`

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import imageschema_ground as isn  # noqa: E402
from rdflib import Graph  # noqa: E402

_PREFIX = """
@prefix isn: <https://ontology.socioprophet.ai/imageschemanet#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
isn:ImageSchema a owl:Class .
isn:CONTAINMENT a owl:Class ; rdfs:subClassOf isn:ImageSchema ; rdfs:label "CONTAINMENT" ;
    isn:hasCoreSP isn:Interior .
isn:Interior a owl:Class .
isn:activates a owl:ObjectProperty .
isn:lexicalSenseActivation rdfs:subPropertyOf isn:activates .
"""


def _graph(body: str) -> Graph:
    g = Graph()
    g.parse(data=_PREFIX + body, format="turtle")
    return g


def test_shipped_cartridge_is_conformant():
    g = isn.load()
    assert isn.verify(g) == []


def test_shipped_golden_groundings_resolve():
    g = isn.load()
    assert isn.selftest(g) == []


def test_lemma_grounds_to_expected_schema():
    g = isn.load()
    assert isn.ground_lemma(g, "contain") == {"CONTAINMENT"}
    assert "SOURCE_PATH_GOAL" in isn.ground_lemma(g, "enter")


def test_sentence_grounding_finds_source_path_goal():
    g = isn.load()
    annot = isn.ground_text(g, "The Obama administration entered into an agreement with Iran")
    schemas = set().union(*annot.values()) if annot else set()
    assert "SOURCE_PATH_GOAL" in schemas


def test_unknown_lemma_grounds_nothing():
    g = isn.load()
    assert isn.ground_lemma(g, "zxqwv") == set()


def test_activator_with_no_schema_fails_verify():
    # An activator that activates nothing recognised — the cartridge lies about coverage.
    g = _graph('isn:lu_bad a isn:LexicalActivator ; rdfs:label "bad" .')
    v = isn.verify(g)
    assert any("activates no known image schema" in x for x in v), v


def test_schema_without_core_primitives_fails_verify():
    g = _graph('isn:NAKED a owl:Class ; rdfs:subClassOf isn:ImageSchema ; rdfs:label "NAKED" .')
    v = isn.verify(g)
    assert any("no core spatial primitives" in x for x in v), v


def test_missing_activation_fails_selftest():
    # A cartridge with the taxonomy but no "contain" activator must fail the golden set.
    g = _graph("")  # only CONTAINMENT class exists, no lexical activators
    assert isn.selftest(g), "golden groundings must fail when activations are absent"
