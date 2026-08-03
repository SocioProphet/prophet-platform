from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RelationshipEffects:
    """Relationship-level effects that are invisible in isolated transaction pricing.

    These parameters deliberately remain transparent and auditable. They let the
    reference engine show why relationship-level pricing is not a blind weighted
    average of instrument-level break-even rates.
    """

    capital_diversification_factor: float = 0.0
    collateral_overlap_factor: float = 0.0
    utilization_interaction_bps: float = 0.0
    franchise_credit_bps: float = 0.0
    capital_hurdle_rate: float = 0.12


def _weighted_average(items: Iterable[dict], value_key: str, weight_key: str = "balance") -> float:
    total_weight = sum(float(item.get(weight_key, 0.0)) for item in items)
    if total_weight <= 0.0:
        return 0.0
    return sum(float(item.get(value_key, 0.0)) * float(item.get(weight_key, 0.0)) for item in items) / total_weight


def relationship_required_rate(transactions: list[dict], effects: RelationshipEffects) -> dict:
    """Compute a first-pass relationship-level profit-implied required rate.

    Inputs are transaction-level economics with at least:
    - balance
    - break_even_rate
    - capital
    - expected_loss
    - utilization
    - collateral_set_id

    The result decomposes the relationship-level required rate into:
    - weighted instrument break-even rate
    - capital diversification credit
    - collateral overlap charge
    - utilization interaction charge
    - franchise / cross-sell credit
    """
    if not transactions:
        raise ValueError("transactions must not be empty")

    total_balance = sum(float(tx.get("balance", 0.0)) for tx in transactions)
    if total_balance <= 0.0:
        raise ValueError("total relationship balance must be positive")

    base_rate = _weighted_average(transactions, "break_even_rate")
    weighted_utilization = _weighted_average(transactions, "utilization")

    gross_capital = sum(float(tx.get("capital", 0.0)) for tx in transactions)
    diversification_factor = max(0.0, min(1.0, effects.capital_diversification_factor))
    capital_diversification_credit = (gross_capital * diversification_factor * effects.capital_hurdle_rate) / total_balance

    collateral_ids = [str(tx.get("collateral_set_id", "")) for tx in transactions]
    counts = Counter(collateral_ids)
    overlapped_ids = {cid for cid, count in counts.items() if cid and count > 1}
    overlap_balance = sum(float(tx.get("balance", 0.0)) for tx in transactions if str(tx.get("collateral_set_id", "")) in overlapped_ids)
    overlap_share = overlap_balance / total_balance
    expected_loss_rate = sum(float(tx.get("expected_loss", 0.0)) for tx in transactions) / total_balance
    collateral_overlap_charge = effects.collateral_overlap_factor * overlap_share * expected_loss_rate

    utilization_interaction_charge = (effects.utilization_interaction_bps / 10000.0) * weighted_utilization
    franchise_credit = effects.franchise_credit_bps / 10000.0

    required_rate = (
        base_rate
        - capital_diversification_credit
        + collateral_overlap_charge
        + utilization_interaction_charge
        - franchise_credit
    )

    return {
        "total_balance": total_balance,
        "weighted_instrument_break_even_rate": base_rate,
        "weighted_utilization": weighted_utilization,
        "gross_capital": gross_capital,
        "capital_diversification_credit": capital_diversification_credit,
        "collateral_overlap_share": overlap_share,
        "collateral_overlap_charge": collateral_overlap_charge,
        "utilization_interaction_charge": utilization_interaction_charge,
        "franchise_credit": franchise_credit,
        "relationship_required_rate": required_rate,
    }
