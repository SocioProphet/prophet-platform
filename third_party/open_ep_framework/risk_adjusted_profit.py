"""Risk-adjusted profit / RAROC contract (RAP-1), grounded on Economic Prophet.

This contract computes economic profit (EP) and RAROC on top of the estate's
residual-value / conservation engine, and it does so for BOTH economic profit and
epistemic profit with the same machinery (the Economia Mentium binding).

What it reuses (consume, do not reinvent)
-----------------------------------------
  * ``uvmc.reconcile_ep_components`` -- the canonical EP identity
        EP = revenue - expected_loss - expense - funding_costs
             + funding_credits - taxes - capital_charge.
  * ``settlement`` (IC-1, economic-prophet#39) -- the conservation law and its
        receipt spine (FIPS SHA-256, ``sha256:`` prefix). Org/entity decomposition
        reconciliation is expressed AS a conservation settlement: the parent EP is
        the single inflow, each child EP an outflow; a cut whose children do not
        sum to the parent fails ``settle`` and is REJECTED. We do not reinvent the
        invariant -- we denominate a new quantity ("economic_profit") in it.
  * ``risk_measures`` (RM-1) -- the unified risk-measure family. EconomicCapital
        for RAROC defaults to a coherent measure (ES / spectral) over a fitted or
        simulated loss distribution F.

Model
-----
  EconomicCapital = credit + market + operating + business + other risk capital
        (optionally a coherent risk measure over F supplies / augments a component).
  CapitalCharge   = HurdleRate * EconomicCapital.
  RiskAdjustedReturn = revenue - expected_loss - expense - funding_costs
                       + funding_credits - taxes         (== NOPAT here).
  EP    = RiskAdjustedReturn - CapitalCharge             (via reconcile_ep_components).
  RAROC = RiskAdjustedReturn / EconomicCapital ; compared to HurdleRate (RORAC).

Dual scoring (Economia Mentium)
-------------------------------
The identical computation runs in ``scoring_mode: "epistemic"``, where the return
legs carry an epistemic-value delta, EconomicCapital is GKN standing (epistemic
capital deployed), and the risk / expected-loss leg is counter-test uncertainty.
Epistemic profit is therefore measured, conserved and receipted with exactly the
same conservation-law RAROC contract as economic profit.

Teeth (verdicts)
----------------
  * VERIFIED -- EP has a real CapitalCharge and RAROC >= HurdleRate.
  * FLAGGED  -- value-destroying arm: RAROC < HurdleRate (returned, not raised).
  * REJECTED (raises) --
        no risk measure supplied;
        no / non-positive economic capital;
        a non-coherent measure used as RAROC capital without an explicit override
            (also emits a coherence warning);
        an org-cut whose child EPs do not reconcile to the parent (IC-1).

Measurement, simulation and audit only -- mirrors the estate boundary: no live
money movement, token issuance, redemption, settlement rails or trading.
"""
from __future__ import annotations

import json
from pathlib import Path

from .risk_measures import (
    LossDistribution,
    NONCOHERENT_KERNELS,
    RiskMeasure,
    risk,
)
from .settlement import SettlementError, _canonical, _sha256, check_conservation
from .uvmc import reconcile_ep_components
from .validation import validate_json_file

_SCHEMA = "schemas/risk_adjusted_profit.schema.json"

DECOMPOSITION_CUTS = {
    "business_unit",
    "product",
    "client_segment",
    "geography",
    "obligor",
    "subportfolio",
    "transaction",
}

_EC_COMPONENTS = ("credit", "market", "operating", "business", "other")


class RiskAdjustedProfitError(ValueError):
    """Raised when an arm cannot be scored under the contract (REJECTED)."""


# --------------------------------------------------------------------------- #
# distribution + risk measure
# --------------------------------------------------------------------------- #
def _build_distribution(spec: dict) -> LossDistribution:
    if "samples" in spec:
        return LossDistribution.from_samples(
            spec["samples"], horizon_days=int(spec.get("horizon_days", 1))
        )
    if "credit" in spec:
        c = spec["credit"]
        return LossDistribution.simulate_credit(
            pd_long=float(c["pd_long"]),
            lgd=float(c["lgd"]),
            ead=float(c["ead"]),
            w_systematic=float(c["w_systematic"]),
            w_idiosyncratic=float(c["w_idiosyncratic"]),
            horizon_days=int(c.get("horizon_days", 1)),
            n_scenarios=int(c.get("n_scenarios", 1000)),
            seed=int(c.get("seed", 0)),
        )
    raise RiskAdjustedProfitError(
        "risk_measure.distribution must provide 'samples' or 'credit' inputs"
    )


def _measure_arm(arm: dict) -> RiskMeasure:
    rm_spec = arm.get("risk_measure")
    if not rm_spec or not rm_spec.get("kernel"):
        # Teeth: a RAROC with no risk measure is not a RAROC.
        raise RiskAdjustedProfitError(
            "REJECTED: no risk measure supplied; RAROC requires a risk measure over a loss distribution"
        )
    distribution = _build_distribution(rm_spec.get("distribution", {}))
    return risk(
        distribution,
        rm_spec["kernel"],
        reference=float(rm_spec.get("reference", 0.0)),
        horizon=float(rm_spec.get("horizon", 1.0)),
        alpha=float(rm_spec.get("alpha", 0.95)),
        order=int(rm_spec.get("order", 2)),
        phi=rm_spec.get("phi"),
    )


# --------------------------------------------------------------------------- #
# economic capital
# --------------------------------------------------------------------------- #
def _economic_capital(arm: dict, measure: RiskMeasure) -> tuple[float, dict, list[str]]:
    rm_spec = arm.get("risk_measure", {})
    ec_spec = arm.get("economic_capital", {})
    components = {name: float(ec_spec.get("components", {}).get(name, 0.0)) for name in _EC_COMPONENTS}
    warnings: list[str] = []

    capital_from_measure = bool(rm_spec.get("capital_from_measure", False))
    if capital_from_measure:
        if measure.family != "tail":
            raise RiskAdjustedProfitError(
                "REJECTED: capital_from_measure requires a tail measure (var/expected_shortfall/spectral)"
            )
        # The measure supplies the credit risk-capital component.
        components["credit"] = measure.value
        if measure.kernel in NONCOHERENT_KERNELS:
            warnings.append(
                f"coherence warning: '{measure.kernel}' is not a coherent risk measure; "
                "economic capital for RAROC should use ES or spectral"
            )
            if not bool(rm_spec.get("allow_noncoherent_capital", False)):
                raise RiskAdjustedProfitError(
                    "REJECTED: non-coherent risk measure used as RAROC economic capital "
                    "without allow_noncoherent_capital override"
                )

    total = sum(components.values())
    if total <= 0.0:
        # Teeth: a RAROC with no economic capital is not a RAROC.
        raise RiskAdjustedProfitError(
            "REJECTED: no (positive) economic capital; RAROC requires an economic-capital denominator"
        )
    breakdown = dict(components)
    breakdown["total"] = total
    return total, breakdown, warnings


# --------------------------------------------------------------------------- #
# single arm
# --------------------------------------------------------------------------- #
_MODE_LABELS = {
    "economic": {
        "return": "risk_adjusted_return",
        "capital": "economic_capital",
        "risk": "loss_distribution",
    },
    "epistemic": {
        "return": "epistemic_value_delta",
        "capital": "gkn_standing_capital",
        "risk": "counter_test_uncertainty",
    },
}


def evaluate_arm(arm: dict, mode: str, arm_id: str) -> dict:
    """Score a single arm: EP, RAROC and a verdict, with a signed receipt."""
    if mode not in _MODE_LABELS:
        raise RiskAdjustedProfitError(f"unknown scoring_mode {mode!r}")

    hurdle = float(arm["hurdle_rate"])
    legs = arm["return_components"]
    revenue = float(legs["revenue"])
    expected_loss = float(legs["expected_loss"])
    expense = float(legs.get("expense", 0.0))
    funding_costs = float(legs.get("funding_costs", 0.0))
    funding_credits = float(legs.get("funding_credits", 0.0))
    taxes = float(legs.get("taxes", 0.0))

    measure = _measure_arm(arm)
    ec_total, ec_breakdown, warnings = _economic_capital(arm, measure)

    if measure.provisional:
        warnings.append(
            f"provisional: loss distribution has n={measure.n_samples} < 30 samples"
        )

    capital_charge = hurdle * ec_total  # CapitalCharge = HurdleRate * EconomicCapital
    ep = reconcile_ep_components(
        {
            "revenue": revenue,
            "expected_loss": expected_loss,
            "expense": expense,
            "funding_costs": funding_costs,
            "funding_credits": funding_credits,
            "taxes": taxes,
            "capital_charge": capital_charge,
        }
    )
    risk_adjusted_return = ep + capital_charge  # == NOPAT
    raroc = risk_adjusted_return / ec_total
    above_hurdle = raroc >= hurdle
    verdict = "verified" if above_hurdle else "flagged"
    if not above_hurdle:
        warnings.append(
            f"flagged value-destroying: RAROC {raroc:.6f} < hurdle {hurdle:.6f}"
        )

    labels = _MODE_LABELS[mode]
    body = {
        "arm_id": arm_id,
        "scoring_mode": mode,
        "interpretation": labels,
        "hurdle_rate": hurdle,
        "economic_capital": ec_breakdown,
        "capital_charge": capital_charge,
        "economic_profit": ep,
        "nopat": risk_adjusted_return,
        "risk_adjusted_return": risk_adjusted_return,
        "raroc": raroc,
        "raroc_above_hurdle": above_hurdle,
        "verdict": verdict,
        "risk_measure": measure.summary(),
        "warnings": warnings,
    }
    # Reuse the estate receipt spine (settlement's canonical-JSON + SHA-256).
    input_hash = _sha256(_canonical(arm))
    receipt = dict(body)
    receipt["input_hash"] = input_hash
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


# --------------------------------------------------------------------------- #
# decomposition + conservation reconciliation (reuses IC-1)
# --------------------------------------------------------------------------- #
def _reconcile_decomposition(parent: dict, children: list[dict], cut: str, tolerance: float,
                             contract_id: str, as_of: str) -> dict:
    """Reconcile child EPs to the parent EP via the IC-1 conservation law.

    Expressed as a settlement: parent EP is the sole inflow, each child EP an
    outflow. ``settle`` REJECTS a non-conserving ledger, so a cut whose children
    do not sum to the parent cannot produce a receipt.
    """
    settlement = {
        "settlement_id": f"{contract_id}:decomp:{cut}",
        "as_of": as_of,
        "conserved_quantity": "economic_profit",
        "tolerance": tolerance,
        "inflows": [
            {"leg_id": "parent", "party": parent["arm_id"], "amount": parent["economic_profit"]}
        ],
        "outflows": [
            {"leg_id": f"child:{c['arm_id']}", "party": c["arm_id"], "amount": c["economic_profit"]}
            for c in children
        ],
    }
    ledger = check_conservation(settlement)
    if not ledger["conserved"]:
        raise RiskAdjustedProfitError(
            f"REJECTED: org-cut '{cut}' does not reconcile to parent under IC-1 "
            f"(parent EP={ledger['sum_in']}, child EP sum={ledger['sum_out']}, "
            f"residual={ledger['residual']} exceeds tolerance {ledger['tolerance']})"
        )
    body = {
        "cut": cut,
        "conservation": ledger,
        "child_count": len(children),
        "child_arm_ids": [c["arm_id"] for c in children],
    }
    receipt = dict(body)
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def evaluate_contract(spec: dict) -> dict:
    """Evaluate a RiskAdjustedProfit contract: parent arm + optional decomposition."""
    mode = spec.get("scoring_mode", "economic")
    contract_id = spec.get("contract_id", "rap")
    as_of = spec.get("as_of", "")

    # Mode-specific provenance teeth (light-touch: presence only).
    provenance = spec.get("provenance", {})
    if mode == "epistemic":
        for required in ("gkn_standing_ref", "counter_test_ref"):
            if not provenance.get(required):
                raise RiskAdjustedProfitError(
                    f"REJECTED: epistemic scoring requires provenance.{required}"
                )

    parent = evaluate_arm(spec["arm"], mode, spec["arm"].get("arm_id", contract_id))

    result = {
        "contract_id": contract_id,
        "as_of": as_of,
        "scoring_mode": mode,
        "arm": parent,
    }

    decomposition = spec.get("decomposition")
    if decomposition:
        cut = decomposition["cut"]
        if cut not in DECOMPOSITION_CUTS:
            raise RiskAdjustedProfitError(
                f"REJECTED: unknown decomposition cut {cut!r}; allowed: {sorted(DECOMPOSITION_CUTS)}"
            )
        tolerance = float(decomposition.get("tolerance", 1e-6))
        children = [
            evaluate_arm(child, mode, child.get("arm_id", f"child-{i}"))
            for i, child in enumerate(decomposition["children"])
        ]
        reconciliation = _reconcile_decomposition(
            parent, children, cut, tolerance, contract_id, as_of
        )
        result["decomposition"] = {
            "cut": cut,
            "children": children,
            "reconciliation": reconciliation,
        }
    return result


def run_risk_adjusted_profit(path: str) -> dict:
    """Load, schema-validate and evaluate a RiskAdjustedProfit contract fixture."""
    validate_json_file(path, _SCHEMA)
    spec = json.loads(Path(path).read_text())
    return evaluate_contract(spec)
