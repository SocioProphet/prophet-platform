"""Matched-maturity Fund Transfer Pricing + separation-theorem decomposition (FTP-1).

This layer builds on the term-structure calculus (``term_calculus``) and the IC-1
conservation law (``settlement``); it does not reinvent either.

Matched-maturity FTP
--------------------
An ``FTPCurve`` is the reference funding curve (SOFR/OIS/swap points by tenor). It
lives on the SAME tenor axis as ``term_calculus`` cash-flow schedules. ``assign_ftp``
prices every cash flow at the curve point matching its repricing/maturity tenor -- a
5y cash flow is transfer-priced at the 5y point, NOT overnight -- and returns the
balance/PV-weighted transfer rate. Funding cost and funding credit that feed the EP
identity are ``transfer_rate * balance``.

Separation theorem
------------------
A unit's net interest margin is separated from the funding book: each unit keeps only
its spread to the matched-maturity curve, and the Treasury book owns the residual
(structural rate mismatch + liquidity + basis). By construction

    NIM = sum(unit spreads) + Treasury residual

which is an IC-1 conservation identity (reused, not reinvented): the decomposition is
settled AS a conservation ledger. Two teeth:

  * A unit funded at an off-market FTP rate (booked != matched-maturity) without the
    difference being booked to Treasury is a hidden cross-subsidy -> REJECTED.
  * The Treasury residual's declared components (structural / liquidity / basis) must
    reconcile to the computed residual -> otherwise REJECTED.

Measurement/simulation/audit only. Deterministic, stdlib only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .settlement import _canonical, _sha256, check_conservation
from .term_calculus import Cashflow
from .validation import validate_json_file

_SCHEMA = "schemas/ftp_separation.schema.json"


class FTPError(ValueError):
    """Raised when an FTP curve or separation decomposition is invalid (REJECTED)."""


# --------------------------------------------------------------------------- #
# reference curve on the term-structure axis
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FTPCurve:
    """Reference funding curve: (tenor_years, rate) points, tenor-ascending."""

    points: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if len(self.points) < 1:
            raise FTPError("FTP curve requires at least one point")
        tenors = [t for t, _ in self.points]
        if tenors != sorted(tenors):
            raise FTPError("FTP curve points must be sorted by ascending tenor")
        if any(t <= 0 for t in tenors):
            raise FTPError("FTP curve tenors must be positive")

    @classmethod
    def from_points(cls, points) -> "FTPCurve":
        return cls(tuple((float(p["tenor"]), float(p["rate"])) for p in points))


def curve_rate(curve: FTPCurve, tenor: float) -> float:
    """The matched-maturity rate at ``tenor`` (linear interpolation, flat extrapolation)."""
    pts = curve.points
    if tenor <= pts[0][0]:
        return pts[0][1]
    if tenor >= pts[-1][0]:
        return pts[-1][1]
    for (t0, r0), (t1, r1) in zip(pts, pts[1:]):
        if t0 <= tenor <= t1:
            frac = (tenor - t0) / (t1 - t0)
            return r0 + frac * (r1 - r0)
    return pts[-1][1]


def _flows(schedule) -> list[Cashflow]:
    return [c if isinstance(c, Cashflow) else Cashflow(float(c["tenor"]), float(c["amount"]))
            for c in schedule]


def assign_ftp(cashflow_schedule, curve: FTPCurve) -> dict:
    """Assign a matched-maturity transfer rate to a cash-flow schedule.

    Each flow is priced at the curve point matching its tenor; the schedule transfer
    rate is the PV-weighted blend. A single bullet at tenor T returns exactly the
    curve rate at T (matched-maturity, asserted by tests).
    """
    flows = _flows(cashflow_schedule)
    if not flows:
        raise FTPError("cash-flow schedule must be non-empty")
    per_flow = []
    num = 0.0
    den = 0.0
    for f in flows:
        matched = curve_rate(curve, f.tenor)
        df = 1.0 / (1.0 + matched) ** f.tenor
        weight = abs(f.amount) * df
        per_flow.append({"tenor": f.tenor, "amount": f.amount, "matched_ftp_rate": matched})
        num += matched * weight
        den += weight
    transfer_rate = num / den if den else 0.0
    return {"transfer_rate": transfer_rate, "per_flow": per_flow}


def funding_cost(balance: float, transfer_rate: float) -> float:
    """FundingCost fed to the EP identity: transfer_rate * balance (asset funding)."""
    return transfer_rate * balance


def funding_credit(balance: float, transfer_rate: float) -> float:
    """FundingCredit fed to the EP identity: transfer_rate * balance (deposit funding)."""
    return transfer_rate * balance


# --------------------------------------------------------------------------- #
# separation-theorem decomposition (reconciled under IC-1)
# --------------------------------------------------------------------------- #
def separation_decomposition(book: dict) -> dict:
    """Decompose net interest margin into unit spreads + Treasury residual.

    Rejects a hidden cross-subsidy and a Treasury residual whose declared components
    do not reconcile to the computed residual. Emits a conservation receipt.
    """
    curve = FTPCurve.from_points(book["curve"]["points"])
    tolerance = float(book.get("tolerance", 1e-6))
    assets = book.get("assets", [])
    liabilities = book.get("liabilities", [])

    unit_spreads: list[dict] = []
    nim = 0.0
    treasury_ftp = 0.0  # sum(booked_a * bal_a) - sum(booked_l * bal_l)

    def _resolve_ftp(item, matched, side):
        booked = float(item.get("booked_ftp_rate", matched))
        if abs(booked - matched) > 1e-12 and not bool(item.get("treasury_absorbs_cross_subsidy", False)):
            raise FTPError(
                f"REJECTED: cross-subsidy on {side} unit {item.get('unit')!r}: booked FTP "
                f"{booked} != matched-maturity rate {matched} (tenor {item.get('tenor')}) "
                "without booking the difference to Treasury"
            )
        return booked

    for a in assets:
        bal = float(a["balance"])
        matched = curve_rate(curve, float(a["tenor"]))
        booked = _resolve_ftp(a, matched, "asset")
        spread = (float(a["customer_rate"]) - booked) * bal
        unit_spreads.append({"unit": a["unit"], "side": "asset", "spread": spread,
                             "matched_ftp_rate": matched, "booked_ftp_rate": booked})
        nim += float(a["customer_rate"]) * bal
        treasury_ftp += booked * bal

    for l in liabilities:
        bal = float(l["balance"])
        matched = curve_rate(curve, float(l["tenor"]))
        booked = _resolve_ftp(l, matched, "liability")
        spread = (booked - float(l["customer_rate"])) * bal
        unit_spreads.append({"unit": l["unit"], "side": "liability", "spread": spread,
                             "matched_ftp_rate": matched, "booked_ftp_rate": booked})
        nim -= float(l["customer_rate"]) * bal
        treasury_ftp -= booked * bal

    treasury = book.get("treasury", {})
    structural = float(treasury.get("structural", 0.0))
    liquidity = float(treasury.get("liquidity", 0.0))
    basis = float(treasury.get("basis", 0.0))
    declared_residual = structural + liquidity + basis

    # Treasury residual components must reconcile to the computed FTP residual.
    if abs(declared_residual - treasury_ftp) > tolerance:
        raise FTPError(
            f"REJECTED: Treasury residual components (structural+liquidity+basis="
            f"{declared_residual}) do not reconcile to computed residual {treasury_ftp}"
        )

    total_spreads = sum(u["spread"] for u in unit_spreads)

    # NIM conservation via IC-1: inflow NIM, outflows = unit spreads + Treasury residual.
    settlement = {
        "settlement_id": f"{book.get('book_id', 'ftp')}:nim",
        "as_of": book.get("as_of", ""),
        "conserved_quantity": "net_interest_margin",
        "tolerance": tolerance,
        "inflows": [{"leg_id": "nim", "party": "book", "amount": nim}],
        "outflows": (
            [{"leg_id": f"unit:{u['unit']}:{u['side']}", "party": u["unit"], "amount": u["spread"]}
             for u in unit_spreads]
            + [{"leg_id": "treasury_residual", "party": "treasury", "amount": treasury_ftp}]
        ),
    }
    ledger = check_conservation(settlement)
    if not ledger["conserved"]:
        raise FTPError(
            f"REJECTED: separation decomposition does not reconcile to NIM "
            f"(residual {ledger['residual']} exceeds tolerance {tolerance})"
        )

    body = {
        "book_id": book.get("book_id", "ftp"),
        "as_of": book.get("as_of", ""),
        "net_interest_margin": nim,
        "unit_spreads": unit_spreads,
        "total_unit_spreads": total_spreads,
        "treasury_residual": {
            "computed": treasury_ftp,
            "structural": structural,
            "liquidity": liquidity,
            "basis": basis,
        },
        "conservation": ledger,
    }
    receipt = dict(body)
    receipt["input_hash"] = _sha256(_canonical(book))
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def run_ftp_separation(path: str) -> dict:
    """Load, schema-validate and run a separation decomposition fixture."""
    validate_json_file(path, _SCHEMA)
    return separation_decomposition(json.loads(Path(path).read_text()))
