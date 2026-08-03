"""Conservation-law settlement of an economic/agency ledger (IC-1).

Economic Prophet's additive value identity (EP = revenue - expected_loss - expense
- funding_costs + funding_credits - taxes - capital_charge) is a *conservation law*:
value is not created or destroyed by an accounting move, only re-attributed across
legs. This module makes that law enforceable for a settlement.

The invariant, and the teeth:

    A settlement conserves its declared quantity iff
        | sum(inflows.amount) - sum(outflows.amount) | <= tolerance

    A settlement that does NOT conserve is REJECTED (``SettlementError``). There is
    no "settled" receipt for a non-conserving ledger — the engine fails closed.

This is measurement, simulation, and audit only. It deliberately remains a
conservation checker + receipt emitter, NOT a token issuer, redemption engine, or
live-money-movement rail (mirrors the associated-surplus / heller-mesh boundary).

The receipt hashes reuse the estate receipt-spine convention (canonical JSON,
sha256, ``sha256:`` prefix — see prophet-workspace tools/proof-artifact-spine and
prophet-platform apps/receipt-gateway) so a settlement result chains into the same
tamper-evident provenance discipline as the rest of the estate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .validation import validate_json_file

_SCHEMA = "schemas/conservation_settlement.schema.json"


class SettlementError(ValueError):
    """Raised when a settlement fails to conserve its declared quantity."""


def _sha256(text: str) -> str:
    """Estate receipt-spine hash: ``sha256:`` + hex digest (FIPS SHA-256)."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(obj: dict) -> str:
    """Deterministic JSON for hashing (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_settlement(path: str) -> dict:
    """Load and schema-validate a conservation-settlement fixture."""
    validate_json_file(path, _SCHEMA)
    return json.loads(Path(path).read_text())


def _leg_total(legs: list[dict]) -> float:
    return sum(float(leg["amount"]) for leg in legs)


def check_conservation(settlement: dict) -> dict:
    """Compute the conservation ledger for a settlement without emitting a receipt.

    Returns a dict with ``sum_in``, ``sum_out``, ``residual`` (in - out),
    ``tolerance`` and ``conserved`` (bool). Does not raise; use for reporting.
    """
    sum_in = _leg_total(settlement["inflows"])
    sum_out = _leg_total(settlement["outflows"])
    residual = sum_in - sum_out
    tolerance = float(settlement["tolerance"])
    return {
        "conserved_quantity": settlement["conserved_quantity"],
        "sum_in": sum_in,
        "sum_out": sum_out,
        "residual": residual,
        "tolerance": tolerance,
        "conserved": abs(residual) <= tolerance,
    }


def settle(settlement: dict) -> dict:
    """Settle a ledger under the conservation law, emitting a signed receipt.

    Enforces the invariant: a non-conserving settlement is REJECTED with
    ``SettlementError``. On success returns a receipt carrying the conservation
    ledger plus input/output/receipt hashes (estate receipt-spine convention).
    """
    ledger = check_conservation(settlement)
    if not ledger["conserved"]:
        raise SettlementError(
            f"settlement {settlement['settlement_id']!r} does not conserve "
            f"{ledger['conserved_quantity']!r}: sum_in={ledger['sum_in']} "
            f"sum_out={ledger['sum_out']} residual={ledger['residual']} "
            f"exceeds tolerance {ledger['tolerance']}"
        )

    input_hash = _sha256(_canonical(settlement))
    body = {
        "settlement_id": settlement["settlement_id"],
        "as_of": settlement["as_of"],
        "settlement_status": "settled",
        "conservation": ledger,
        "n_inflows": len(settlement["inflows"]),
        "n_outflows": len(settlement["outflows"]),
        "input_hash": input_hash,
    }
    receipt = dict(body)
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def run_settlement(path: str) -> dict:
    """Load, validate, and settle a fixture. Rejects non-conserving ledgers."""
    settlement = load_settlement(path)
    return settle(settlement)
