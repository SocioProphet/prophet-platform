"""Swaps / futures as zeroing derivatives -- hedge ratios from the calculus (HDG-1).

A hedge zeroes a derivative of value w.r.t. a factor. The hedge ratio is read from
``term_calculus``: the first derivative (DV01 / duration) sets a DV01-neutral hedge;
the second derivative (convexity) is what a linear hedge (swap / futures) cannot
neutralize, so a convexity mismatch leaves 2nd-order P&L. Nothing here reinvents the
calculus -- it consumes ``term_calculus``.

Teeth:
  * a DV01-neutral hedge drives the net first derivative to ~0 under a curve bump
    (finite-difference reprice);
  * a convexity-mismatched linear hedge still shows 2nd-order P&L (asserted residual).

Futures are a margined linear rate/commodity hedge marked-to-market daily; a basic
variation-margin representation is included. Deterministic, stdlib only.
"""
from __future__ import annotations

from .term_calculus import (
    Cashflow,
    effective_convexity,
    finite_difference,
    modified_duration,
    price,
    second_difference,
)


class HedgeError(ValueError):
    pass


def _flows(schedule) -> list[Cashflow]:
    return [c if isinstance(c, Cashflow) else Cashflow(float(c["tenor"]), float(c["amount"]))
            for c in schedule]


def dv01(schedule, y: float) -> float:
    """Dollar value of 1bp: modified_duration * price * 1e-4 (a first derivative)."""
    flows = _flows(schedule)
    return modified_duration(flows, y) * price(flows, y) * 1e-4


def hedge_notional(book, y_book: float, instrument, y_instrument: float) -> dict:
    """Signed instrument notional (per unit-notional instrument) to zero book DV01.

    ``notional = -DV01_book / DV01_instrument_per_unit``: the hedge's first derivative
    exactly offsets the book's. Convexity is reported so a mismatch is visible.
    """
    book_flows = _flows(book)
    inst_flows = _flows(instrument)
    dv01_inst = dv01(inst_flows, y_instrument)
    if dv01_inst == 0:
        raise HedgeError("hedge instrument has zero DV01; cannot form a hedge ratio")
    dv01_book = dv01(book_flows, y_book)
    notional = -dv01_book / dv01_inst
    return {
        "notional": notional,
        "dv01_book": dv01_book,
        "dv01_instrument_per_unit": dv01_inst,
        "book_convexity": effective_convexity(lambda yy: price(book_flows, yy), y_book),
        "instrument_convexity": effective_convexity(lambda yy: price(inst_flows, yy), y_instrument),
    }


def net_first_derivative(book, instrument, notional: float, y: float, bump: float = 1e-4) -> float:
    """dP/dy of the hedged portfolio (book + notional*instrument) by bump-and-reprice."""
    book_flows = _flows(book)
    inst_flows = _flows(instrument)
    reprice = lambda yy: price(book_flows, yy) + notional * price(inst_flows, yy)
    return finite_difference(reprice, y, bump)


def net_second_derivative(book, instrument, notional: float, y: float, bump: float = 1e-3) -> float:
    """d2P/dy2 of the hedged portfolio (residual convexity a linear hedge leaves)."""
    book_flows = _flows(book)
    inst_flows = _flows(instrument)
    reprice = lambda yy: price(book_flows, yy) + notional * price(inst_flows, yy)
    return second_difference(reprice, y, bump)


def hedged_pnl(book, instrument, notional: float, y: float, dy: float) -> float:
    """Actual reprice P&L of the hedged portfolio under a finite curve bump ``dy``."""
    book_flows = _flows(book)
    inst_flows = _flows(instrument)

    def reprice(yy):
        return price(book_flows, yy) + notional * price(inst_flows, yy)

    return reprice(y + dy) - reprice(y)


def futures_variation_margin(entry_price: float, price_path, contract_size: float,
                             position: float) -> dict:
    """Daily mark-to-market of a margined linear futures hedge.

    ``position`` is signed (long > 0, short < 0). Returns per-day variation margin and
    the cumulative total; the cumulative equals the linear payoff to the terminal price.
    """
    path = [float(p) for p in price_path]
    daily = []
    prev = entry_price
    for p in path:
        daily.append(position * contract_size * (p - prev))
        prev = p
    total = sum(daily)
    linear_payoff = position * contract_size * (path[-1] - entry_price) if path else 0.0
    return {"daily_variation_margin": daily, "total": total, "linear_payoff": linear_payoff}
