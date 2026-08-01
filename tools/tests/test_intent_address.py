"""Tests for the 23x6 -> coordinate-algebra bridge.

Proves the flat grid gains exactly what it lacked: a metric on its rows, an
abstraction layer (the meta row is genuinely second-order), and — the payoff — the
`sense` wiring gap surfacing as a first-class abstention instead of a mis-route.
"""

from __future__ import annotations

import pytest

from tools.semantic_algebra import BOTTOM, LayerError
from tools.intent_address import (
    COLUMNS,
    INTENT_PRIMARY,
    META_ROW,
    build_intent_addresses,
    column_fill,
    intent_distance,
    route,
)


def _addrs():
    return build_intent_addresses()


# -- coverage & shape ------------------------------------------------------- #


def test_every_row_addressed_and_distinct():
    addrs = _addrs()
    assert len(addrs) == len(INTENT_PRIMARY) + 1  # topics + the meta row
    terms = [a.term for a in addrs.values()]
    assert len({t.code() for t in terms}) == len(terms)  # all distinct


def test_topic_rows_are_layer_2_meta_is_layer_3():
    addrs = _addrs()
    for name, addr in addrs.items():
        if name == META_ROW:
            assert addr.term.layer == 3  # second-order: operand is an action
        else:
            assert addr.term.layer == 2


# -- the metric the flat grid did not have ---------------------------------- #


def test_same_column_intents_are_nearer_than_cross_column():
    addrs = _addrs()
    same = intent_distance(addrs["qa_over_doc"], addrs["research_lookup"])  # both retrieve
    cross = intent_distance(addrs["qa_over_doc"], addrs["file_ingest"])      # retrieve vs sense
    assert same == 1
    assert cross == 2
    assert same < cross


# -- the meta row is second-order, comparable only to its own order --------- #


def test_meta_row_is_not_comparable_to_a_topic_row():
    addrs = _addrs()
    with pytest.raises(LayerError):
        intent_distance(addrs[META_ROW], addrs["qa_over_doc"])  # layer 3 vs 2


# -- tiered routing, and the sense gap as abstention ------------------------ #


def test_route_grounds_a_column_query_to_an_intent_in_that_column():
    addrs = _addrs()
    assert route("sense", addrs) == addrs["file_ingest"].term
    assert route("transform", addrs) is not BOTTOM  # transform is well-populated


def test_sense_gap_becomes_a_first_class_abstention():
    addrs = _addrs()
    without_sense = {k: v for k, v in addrs.items() if k != "file_ingest"}
    # with the one sense intent removed, a world:read query cannot route -> BOTTOM,
    # not a silent mis-route to some other column.
    assert route("sense", without_sense) is BOTTOM


# -- the column asymmetry finding, reproduced structurally ------------------ #


def test_sense_is_the_thinnest_column():
    fill = column_fill(_addrs())
    assert fill["sense"] == 1
    assert fill["sense"] == min(fill.values())
    # every column admits at least one intent — no dead columns
    assert all(count >= 1 for count in fill.values())
    assert set(fill) == set(COLUMNS)
