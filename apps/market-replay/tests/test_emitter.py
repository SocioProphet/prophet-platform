"""Unit gate for the contract + emitter core: NOTHING NON-CONFORMANT REACHES THE LOG.

The hellgraph door is faked. The fake records every write verbatim, so the assertions
pin the exact node/edge shapes the platform log (and, via the W1.1 materializer,
ClickHouse) will carry — and the failure tests prove fail-closed validation and
retry-without-duplicates under an outage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_replay import contract, emitter as emitter_mod  # noqa: E402
from market_replay.contract import build_event, flatten, local_id, validate_event  # noqa: E402
from market_replay.emitter import (  # noqa: E402
    EDGE_LABEL, EVENT_LABEL, SYMBOL_LABEL, EmitError, ReplayEmitter,
)
from market_replay.generator import Tick, TickGenerator  # noqa: E402

SYMBOLS = ["SP:AAA", "SP:BBB", "SP:CCC"]
WALL = "2026-07-29T12:00:00.000Z"


class FakeWriter:
    """Records post_node/post_edge verbatim; `down` fails everything, `fail_edges`
    fails only edges (the half-emitted-item case)."""

    def __init__(self):
        self.nodes: list[tuple] = []
        self.edges: list[tuple] = []
        self.down = False
        self.fail_edges = False

    def post_node(self, node_id, labels, properties):
        if self.down:
            raise EmitError("hellgraph down")
        self.nodes.append((node_id, list(labels), dict(properties)))

    def post_edge(self, label, from_id, to_id):
        if self.down or self.fail_edges:
            raise EmitError("hellgraph down")
        self.edges.append((label, from_id, to_id))


def make(writer=None) -> tuple[ReplayEmitter, FakeWriter]:
    w = writer or FakeWriter()
    em = ReplayEmitter(generator=TickGenerator(SYMBOLS, seed=42), writer=w,
                       clock=lambda: WALL)
    return em, w


# ── the contract itself ──────────────────────────────────────────────────────


def test_generated_events_validate_against_the_vendored_schema():
    gen = TickGenerator(SYMBOLS, seed=42)
    for _ in range(10):
        for tick in gen.next_batch():
            validate_event(build_event(tick, WALL))     # raises on any drift


def test_event_shape_is_the_spec_envelope():
    ev = build_event(Tick(symbol="SP:AAA", seq=7, price=101.25, volume=42), WALL)
    assert ev["id"] == "urn:srcos:market-data-event:mde-SP-AAA-000007"
    assert ev["type"] == "MarketDataEvent" and ev["specVersion"] == "0.1.0"
    assert ev["instrumentRef"] == "SP:AAA" and ev["eventKind"] == "trade"
    assert ev["logicalTime"] == 7 and ev["sequenceRef"] == 7
    assert ev["qualityFlags"] == ["synthetic"]          # unmistakably not a real feed
    assert ev["canonicalPayload"]["normalizationRegime"]  # schema invariant: declared
    validate_event(ev)


@pytest.mark.parametrize("mutate", [
    lambda e: e.pop("instrumentRef"),                       # missing required
    lambda e: e.pop("canonicalPayload"),                    # missing required
    lambda e: e.update(eventKind="vibes"),                  # outside the enum
    lambda e: e.update(id="urn:srcos:market-data-event:mde-SP:AAA-7"),  # ':' breaks the URN charset
    lambda e: e.update(specVersion="9.9.9"),                # const violation
    lambda e: e.update(bonusField=True),                    # additionalProperties: false
])
def test_malformed_events_are_rejected(mutate):
    ev = build_event(Tick(symbol="SP:AAA", seq=1, price=100.0, volume=1), WALL)
    mutate(ev)
    with pytest.raises(jsonschema.ValidationError):
        validate_event(ev)


def test_startup_check_passes_for_this_producer():
    em, _ = make()
    em.startup_check()                                  # must not raise


# ── emission shapes ──────────────────────────────────────────────────────────


def test_run_once_posts_symbol_nodes_event_nodes_and_aboutSymbol_edges():
    em, w = make()
    result = em.run_once()

    assert result.generated == 3 and result.emitted == 3
    assert result.validation_failures == 0 and result.pending == 0
    assert result.hellgraph_ok is True and result.last_seq == 1

    symbol_nodes = [n for n in w.nodes if SYMBOL_LABEL in n[1]]
    event_nodes = [n for n in w.nodes if EVENT_LABEL in n[1]]
    assert [n[0] for n in symbol_nodes] == SYMBOLS       # once each, id = raw symbol
    assert [n[0] for n in event_nodes] == [local_id(s, 1) for s in SYMBOLS]

    nid, labels, props = event_nodes[0]
    assert nid == "mde-SP-AAA-000001"
    assert labels == [EVENT_LABEL, "SP:AAA"]
    assert props["eventId"] == "urn:srcos:market-data-event:mde-SP-AAA-000001"
    assert props["schemaVersion"] == "0.1.0" and props["symbol"] == "SP:AAA"
    assert isinstance(props["price"], float) and isinstance(props["volume"], int)
    assert props["eventTime"] == WALL and props["ingestTime"] == WALL
    assert props["synthetic"] is True
    embedded = json.loads(props["event"])               # the log carries the OBJECT
    validate_event(embedded)
    assert embedded["id"] == props["eventId"]

    assert w.edges == [(EDGE_LABEL, local_id(s, 1), s) for s in SYMBOLS]


def test_symbol_nodes_are_created_once_not_per_batch():
    em, w = make()
    em.run_once()
    em.run_once()
    assert len([n for n in w.nodes if SYMBOL_LABEL in n[1]]) == 3
    assert len([n for n in w.nodes if EVENT_LABEL in n[1]]) == 6   # 2 batches × 3


# ── fail-closed validation ───────────────────────────────────────────────────


def test_invalid_event_is_counted_and_never_emitted(monkeypatch):
    """Corrupt ONE symbol's event at the source: it must be dropped loudly while the
    rest of the batch still lands — fail-closed, not fail-everything."""
    real = contract.build_event

    def corrupting(tick, wall_time):
        ev = real(tick, wall_time)
        if tick.symbol == "SP:BBB":
            del ev["instrumentRef"]                    # now schema-invalid
        return ev

    monkeypatch.setattr(emitter_mod, "build_event", corrupting)
    em, w = make()
    result = em.run_once()

    assert result.validation_failures == 1
    assert result.emitted == 2 and result.pending == 0
    event_nodes = [n[0] for n in w.nodes if EVENT_LABEL in n[1]]
    assert event_nodes == ["mde-SP-AAA-000001", "mde-SP-CCC-000001"]   # SP:BBB absent
    assert all(frm != local_id("SP:BBB", 1) for _, frm, _to in w.edges)


# ── hellgraph outage: retry, no crash, no duplicates, no gaps ────────────────


def test_outage_keeps_batch_pending_then_drains_without_gaps():
    em, w = make()
    w.down = True
    r1 = em.run_once()                                  # symbols can't even be ensured
    assert r1.hellgraph_ok is False and r1.emitted == 0

    w.down = False
    r2 = em.run_once()                                  # heals: symbols + batch 1
    assert r2.hellgraph_ok is True and r2.emitted == 3 and r2.last_seq == 1

    w.down = True
    r3 = em.run_once()                                  # batch 2 generated, all pending
    assert r3.generated == 3 and r3.emitted == 0 and r3.pending == 3

    r4 = em.run_once()                                  # still down: NOTHING new generated
    assert r4.generated == 0 and r4.pending == 3        # bounded memory, gapless stream

    w.down = False
    r5 = em.run_once()                                  # drains the pending batch
    assert r5.emitted == 3 and r5.pending == 0 and r5.last_seq == 2

    seqs = sorted(int(n[0].rsplit("-", 1)[1]) for n in w.nodes if EVENT_LABEL in n[1])
    assert seqs == [1, 1, 1, 2, 2, 2]                   # no seq skipped, none duplicated


def test_half_emitted_item_never_resends_the_landed_node():
    em, w = make()
    w.fail_edges = True
    r1 = em.run_once()
    assert r1.emitted == 0 and r1.pending == 3          # first node landed, edge didn't
    nodes_before = len(w.nodes)

    w.fail_edges = False
    r2 = em.run_once()
    assert r2.emitted == 3 and r2.pending == 0

    first = local_id("SP:AAA", 1)
    assert len([n for n in w.nodes if n[0] == first]) == 1     # node POSTed exactly once
    assert len([e for e in w.edges if e[1] == first]) == 1     # edge exactly once
    assert len(w.nodes) == nodes_before + 2             # only the two unlanded nodes followed
