"""Determinism is the acceptance bar: the whole replay stream must be a pure function
of (seed, symbol, seq) — never of wall clock, host, process hash seed, or list order."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_replay.generator import Tick, TickGenerator, base_price  # noqa: E402

SYMBOLS = ["SP:AAA", "SP:BBB", "SP:CCC"]


def stream(gen: TickGenerator, batches: int) -> list[Tick]:
    out: list[Tick] = []
    for _ in range(batches):
        out.extend(gen.next_batch())
    return out


def test_same_seed_produces_identical_streams():
    a = stream(TickGenerator(SYMBOLS, seed=42), 20)
    b = stream(TickGenerator(SYMBOLS, seed=42), 20)
    assert a == b                                   # Tick is frozen → value equality
    assert len(a) == 60


def test_different_seed_diverges():
    a = stream(TickGenerator(SYMBOLS, seed=42), 5)
    b = stream(TickGenerator(SYMBOLS, seed=43), 5)
    assert a != b


def test_symbol_paths_independent_of_list_order():
    fwd = stream(TickGenerator(SYMBOLS, seed=42), 10)
    rev = stream(TickGenerator(list(reversed(SYMBOLS)), seed=42), 10)
    by_symbol = lambda ticks, s: [t for t in ticks if t.symbol == s]  # noqa: E731
    for s in SYMBOLS:
        assert by_symbol(fwd, s) == by_symbol(rev, s)


def test_seq_is_per_symbol_monotonic_from_one_and_prices_stay_positive():
    ticks = stream(TickGenerator(SYMBOLS, seed=7), 50)
    for s in SYMBOLS:
        seqs = [t.seq for t in ticks if t.symbol == s]
        assert seqs == list(range(1, 51))
    assert all(t.price > 0 for t in ticks)
    assert all(1 <= t.volume <= 1_000 for t in ticks)


def test_base_price_is_stable_and_in_band():
    assert base_price("SP:AAA") == base_price("SP:AAA")
    for s in SYMBOLS:
        assert 50.0 <= base_price(s) < 150.0


def test_empty_symbol_set_is_refused():
    with pytest.raises(ValueError):
        TickGenerator([], seed=1)
