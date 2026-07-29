"""Deterministic synthetic tick source — a seeded random walk per symbol.

SYNTHETIC BY CONSTRUCTION: no real market data enters this service. Prices start at a
base derived from sha256(symbol) (never Python's salted hash — PYTHONHASHSEED would
break replay), step by a seeded Gaussian return, and every downstream event carries
qualityFlags=["synthetic"]. The point of W1.2 is the CONTRACT — the first
sourceos-spec-conformant MarketDataEvent objects flowing through the platform log —
not the data.

Determinism is the acceptance bar: each symbol owns a private random.Random seeded
with "<seed>:<symbol>", so a symbol's price path depends only on (seed, symbol, seq) —
not on the symbol list's order, the interval, or the wall clock. Two generators with
the same seed produce byte-identical tick streams (the unit-test gate), which makes
every row the materializer lands in ClickHouse replayable from first principles.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

# Walk parameters — small per-tick moves so long runs stay in a plausible band.
STEP_SIGMA = 0.005          # stddev of the per-tick fractional return
PRICE_FLOOR = 0.01          # a random walk must never emit a non-positive price
VOLUME_RANGE = (1, 1_000)   # inclusive bounds for the synthetic trade size


def base_price(symbol: str) -> float:
    """Stable starting price in [50, 150) derived from sha256(symbol) — identical on
    every host and run, independent of process hash randomization."""
    digest = hashlib.sha256(symbol.encode("utf-8")).digest()
    return 50.0 + (int.from_bytes(digest[:8], "big") % 10_000) / 100.0


@dataclass(frozen=True)
class Tick:
    symbol: str
    seq: int          # per-symbol, monotonically increasing from 1 — the replay clock
    price: float
    volume: int


class TickGenerator:
    """Per-symbol seeded random walk. `next_batch()` yields one Tick per symbol in the
    configured order; per-symbol state is independent, so adding or reordering symbols
    never perturbs another symbol's path."""

    def __init__(self, symbols: list[str], seed: int) -> None:
        if not symbols:
            raise ValueError("TickGenerator needs at least one symbol")
        self.symbols = list(symbols)
        self.seed = seed
        self._rng = {s: random.Random(f"{seed}:{s}") for s in self.symbols}
        self._price = {s: base_price(s) for s in self.symbols}
        self._seq = {s: 0 for s in self.symbols}

    def next_tick(self, symbol: str) -> Tick:
        rng = self._rng[symbol]
        step = rng.gauss(0.0, STEP_SIGMA)
        price = max(PRICE_FLOOR, round(self._price[symbol] * (1.0 + step), 4))
        self._price[symbol] = price
        self._seq[symbol] += 1
        return Tick(symbol=symbol, seq=self._seq[symbol], price=price,
                    volume=rng.randint(*VOLUME_RANGE))

    def next_batch(self) -> list[Tick]:
        return [self.next_tick(s) for s in self.symbols]


__all__ = ["Tick", "TickGenerator", "base_price"]
