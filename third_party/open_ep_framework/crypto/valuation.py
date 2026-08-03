"""CryptoAssetValuation contract (CAV-1) -- value criteria that are NOT DCF.

Why crypto needs its own F and its own value criteria
-----------------------------------------------------
A token mostly has no cash flows, so a discounted-cash-flow (DCF) valuation is the
WRONG model: there is nothing to discount. Value instead comes from the protocol
(supply/emission/burn/security budget), on-chain usage (active addresses, TVL, fee
revenue), the network itself (Metcalfe value proportional to n^2; NVT ratio == the
network-value-to-transactions "crypto P/E"), and -- uniquely -- from attention and
narrative (a memetic / information-theoretic value). This contract makes each of
those a transparent, testable scalar, and it REJECTS a cash-flow model asserted on a
no-cash-flow token.

Modified economic profit (the crypto EP identity)
-------------------------------------------------
    modified_ep = fee_revenue - security_cost - emission_dilution - risk_capital

  * ``fee_revenue``       -- annualized protocol fee revenue (the real, earned leg).
  * ``security_cost``     -- the security budget (issuance+fees paid to miners/
                             validators) that pays for the hashrate/stake defending
                             the chain; a cost of doing business, not value to holders.
  * ``emission_dilution`` -- net new issuance charged at price:
                             (circulating_supply*emission_rate - burn_tokens) * price.
                             Deflationary (burn > emission) makes this NEGATIVE, i.e.
                             accretive. A modified-EP that ignores this term is silent
                             inflation and is REJECTED.
  * ``risk_capital``      -- a COHERENT tail-risk charge (Expected Shortfall) over a
                             REFLEXIVE, FAT-TAILED loss distribution F, consumed from
                             the estate risk kernel (RM-1). Reflexivity amplifies vol;
                             a small Student-t df supplies the fat left tail.

Memetic / information-theoretic value (Economia Mentium)
--------------------------------------------------------
Value as attention/narrative, framed as an information-asset: value == epistemic
delta, liquidity == attention/volume. From an attention series it computes a virality
(replication) factor and an information-theoretic epistemic delta (KL of the attention
distribution from its uniform prior, in bits). Learn-don't-match: a memetic value
asserted with NO evidence (empty attention series / no evidence list) is REJECTED --
no bare narrative scores.

Deterministic and stdlib-only. Measurement, simulation and audit only.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from ..risk_measures import LossDistribution, lpm, risk
from ..settlement import _canonical, _sha256
from ..validation import validate_json_file

_SCHEMA = "schemas/crypto_asset_valuation.schema.json"

# Value criteria that are legitimate for a (mostly) no-cash-flow token. DCF is
# deliberately absent: it is the wrong model for an asset with no cash flows.
NETWORK_METHODS = {"network_metcalfe", "nvt", "fee_modified_ep", "memetic"}
CASH_FLOW_METHODS = {"dcf", "ddm", "cash_flow"}


class CryptoValuationError(ValueError):
    """Raised when a token cannot be valued under the contract (REJECTED)."""


# --------------------------------------------------------------------------- #
# reflexive, fat-tailed F -> risk_capital (consume the estate risk kernel RM-1)
# --------------------------------------------------------------------------- #
def _reflexive_loss_distribution(spec: dict) -> LossDistribution:
    """Build a reflexive, fat-tailed RETURN distribution F for the risk kernel.

    Reflexivity (Soros): price and fundamentals feed back on each other, fattening
    and widening the return distribution during self-exciting phases. We model it as
    a volatility amplifier ``sigma_eff = sigma * (1 + reflexivity)`` on a Student-t
    body whose (small) degrees of freedom ``df`` supply the fat left tail. The result
    is a ``LossDistribution`` the RM-1 kernel reads directly for ES / LPM -- we do not
    reinvent the tail math, we shape F for it.
    """
    mu = float(spec.get("mu", 0.0))
    sigma = float(spec.get("sigma", 0.05))
    if sigma <= 0:
        raise CryptoValuationError("reflexive F requires sigma > 0")
    reflexivity = float(spec.get("reflexivity", 0.0))
    if reflexivity < 0:
        raise CryptoValuationError("reflexivity must be >= 0")
    df = float(spec.get("df", 3.0))  # small df == fat tails
    sigma_eff = sigma * (1.0 + reflexivity)
    return LossDistribution.simulate_equity(
        mu=mu,
        sigma=sigma_eff,
        df=df,
        horizon_days=int(spec.get("horizon_days", 1)),
        n_scenarios=int(spec.get("n_scenarios", 2000)),
        seed=int(spec.get("seed", 0)),
    )


def _risk_capital(spec: dict) -> dict:
    """Coherent tail risk capital = ES_fraction(F) * risk_notional (RM-1).

    ``risk_notional`` is the value exposed (e.g. market cap or a position mark).
    Expected Shortfall is coherent (unlike VaR), so this is a defensible capital
    magnitude. LPM_2 (downside deviation squared) is reported alongside so the
    reflexive downside is auditable via the same kernel.
    """
    notional = float(spec.get("risk_notional", 0.0))
    if notional < 0:
        raise CryptoValuationError("risk_notional must be >= 0")
    alpha = float(spec.get("alpha", 0.975))
    F = _reflexive_loss_distribution(spec)
    es = risk(F, "expected_shortfall", alpha=alpha)
    es_fraction = es.value  # per-unit loss fraction from the return F
    lpm2 = lpm(F.samples, tau=float(spec.get("mar", 0.0)), order=2)
    return {
        "risk_capital": es_fraction * notional,
        "es_fraction": es_fraction,
        "alpha": alpha,
        "lpm2_downside": lpm2,
        "reflexivity": float(spec.get("reflexivity", 0.0)),
        "df": float(spec.get("df", 3.0)),
        "coherent": es.coherent,
        "provisional": es.provisional,
        "distribution_id": es.distribution_id,
        "risk_notional": notional,
    }


# --------------------------------------------------------------------------- #
# network value: Metcalfe (proportional to n^2) and NVT (crypto P/E)
# --------------------------------------------------------------------------- #
def _network_value(tokenomics: dict, onchain: dict, network: dict) -> dict:
    """Metcalfe value (proportional to n^2) and NVT ratio, reconciled to inputs."""
    n = float(onchain["active_addresses"])
    if n < 0:
        raise CryptoValuationError("active_addresses must be >= 0")
    k = float(network.get("metcalfe_coefficient", 1.0))
    metcalfe_value = k * n * n  # Metcalfe's law: network value proportional to n^2

    supply = float(tokenomics["circulating_supply"])
    price = float(tokenomics["price"])
    market_cap = supply * price

    tx_volume = float(onchain.get("annual_tx_volume", 0.0))
    if tx_volume <= 0:
        raise CryptoValuationError(
            "NVT requires a positive annual_tx_volume (network throughput)"
        )
    nvt = market_cap / tx_volume  # network-value-to-transactions == crypto P/E

    metcalfe_implied_price = metcalfe_value / supply if supply > 0 else math.inf
    # >1 == market price rich vs Metcalfe-fair; <1 == cheap.
    price_to_metcalfe = price / metcalfe_implied_price if metcalfe_implied_price > 0 else math.inf
    return {
        "active_addresses": n,
        "metcalfe_coefficient": k,
        "metcalfe_value": metcalfe_value,
        "metcalfe_implied_price": metcalfe_implied_price,
        "market_cap": market_cap,
        "annual_tx_volume": tx_volume,
        "nvt_ratio": nvt,
        "price_to_metcalfe": price_to_metcalfe,
    }


# --------------------------------------------------------------------------- #
# modified economic profit
# --------------------------------------------------------------------------- #
def _emission_dilution(tokenomics: dict) -> float:
    """Net-issuance dilution charged at price = (emission - burn) tokens * price.

    Deflationary tokens (burn > emission) yield a NEGATIVE dilution (accretive).
    A positive net emission with no price is silent inflation and is REJECTED by the
    caller, which requires a price whenever emission is present.
    """
    supply = float(tokenomics["circulating_supply"])
    emission_rate = float(tokenomics.get("emission_rate", 0.0))
    burn_tokens = float(tokenomics.get("burn_tokens_annual", 0.0))
    price = float(tokenomics["price"])
    net_new_tokens = supply * emission_rate - burn_tokens
    return net_new_tokens * price


def _modified_ep(spec: dict) -> dict:
    """modified_ep = fee_revenue - security_cost - emission_dilution - risk_capital."""
    tokenomics = spec["tokenomics"]
    onchain = spec["onchain"]

    fee_revenue = float(onchain.get("fee_revenue", 0.0))
    security_cost = float(spec.get("security", {}).get("security_cost", 0.0))
    if security_cost < 0:
        raise CryptoValuationError("security_cost must be >= 0")

    # Teeth: emission dilution may not be silently dropped. A token with net positive
    # emission MUST carry a price so its dilution is charged.
    emission_rate = float(tokenomics.get("emission_rate", 0.0))
    burn_tokens = float(tokenomics.get("burn_tokens_annual", 0.0))
    supply = float(tokenomics["circulating_supply"])
    net_new_tokens = supply * emission_rate - burn_tokens
    if net_new_tokens > 0 and "price" not in tokenomics:
        raise CryptoValuationError(
            "REJECTED: net positive emission with no price is unpriced dilution "
            "(silent inflation); modified-EP must charge emission dilution"
        )
    emission_dilution = _emission_dilution(tokenomics)

    rc = _risk_capital(spec.get("risk", {}))
    risk_capital = rc["risk_capital"]

    modified_ep = fee_revenue - security_cost - emission_dilution - risk_capital
    return {
        "modified_ep": modified_ep,
        "fee_revenue": fee_revenue,
        "security_cost": security_cost,
        "emission_dilution": emission_dilution,
        "net_new_tokens": net_new_tokens,
        "risk_capital": risk_capital,
        "risk": rc,
    }


# --------------------------------------------------------------------------- #
# memetic / information-theoretic value (Economia Mentium)
# --------------------------------------------------------------------------- #
def _memetic_value(memetic: dict) -> dict:
    """Evidence-bound memetic / information value: virality * epistemic delta.

    ``attention_series`` is a time series of an attention/volume proxy (social
    volume, search interest, mentions). We compute:
      * virality      -- replication factor = latest / mean(prior window). >1 == the
                         narrative is spreading faster than its own recent history.
      * epistemic_delta (bits) -- KL(p || uniform) = log2(T) - H(p), where p is the
                         attention distribution over the window: how far the narrative
                         has moved from a flat prior (== information gained).
      * information_value -- virality * epistemic_delta (both evidence-derived).

    Learn-don't-match: an empty attention_series or empty evidence list is REJECTED.
    No bare narrative scores.
    """
    series = [float(x) for x in memetic.get("attention_series", [])]
    evidence = memetic.get("evidence", [])
    if len(series) < 2 or not evidence:
        raise CryptoValuationError(
            "REJECTED: memetic/attention value requires an attention series (>=2 points) "
            "and evidence; a bare narrative score is not admissible"
        )
    if any(x < 0 for x in series):
        raise CryptoValuationError("attention_series values must be >= 0")
    total = sum(series)
    if total <= 0:
        raise CryptoValuationError("attention_series must have positive total attention")

    latest = series[-1]
    prior = series[:-1]
    prior_mean = sum(prior) / len(prior)
    virality = latest / prior_mean if prior_mean > 0 else math.inf

    p = [x / total for x in series]
    entropy_bits = -sum(pi * math.log2(pi) for pi in p if pi > 0)
    max_entropy = math.log2(len(series))
    epistemic_delta = max_entropy - entropy_bits  # KL(p || uniform) in bits, >= 0
    surprise_latest = -math.log2(p[-1]) if p[-1] > 0 else math.inf

    information_value = virality * epistemic_delta
    return {
        "virality": virality,
        "entropy_bits": entropy_bits,
        "epistemic_delta_bits": epistemic_delta,
        "surprise_latest_bits": surprise_latest,
        "information_value": information_value,
        "attention_liquidity": total,
        "evidence_count": len(evidence),
        "evidence": list(evidence),
    }


# --------------------------------------------------------------------------- #
# contract
# --------------------------------------------------------------------------- #
def _guard_model(spec: dict) -> None:
    """Wrong-model guard: a cash-flow (DCF) model on a no-cash-flow token is REJECTED."""
    method = spec.get("valuation_method")
    cash_flow_bearing = bool(spec.get("tokenomics", {}).get("cash_flow_bearing", False))
    if method in CASH_FLOW_METHODS and not cash_flow_bearing:
        raise CryptoValuationError(
            f"REJECTED: valuation_method '{method}' discounts cash flows, but this token "
            "has no cash flows (cash_flow_bearing=false). Use network/fee/memetic criteria "
            f"({sorted(NETWORK_METHODS)}) -- the credit/equity DCF machinery does not apply."
        )
    if method is not None and method not in NETWORK_METHODS and method not in CASH_FLOW_METHODS:
        raise CryptoValuationError(f"unknown valuation_method {method!r}")


def _guard_emission_priced(tokenomics: dict) -> None:
    """Teeth: net positive emission with no price is unpriced dilution (silent inflation)."""
    supply = float(tokenomics["circulating_supply"])
    emission_rate = float(tokenomics.get("emission_rate", 0.0))
    burn_tokens = float(tokenomics.get("burn_tokens_annual", 0.0))
    net_new_tokens = supply * emission_rate - burn_tokens
    if net_new_tokens > 0 and "price" not in tokenomics:
        raise CryptoValuationError(
            "REJECTED: net positive emission with no price is unpriced dilution "
            "(silent inflation); modified-EP must charge emission dilution"
        )


def evaluate_valuation(spec: dict) -> dict:
    """Value a crypto asset under CAV-1: network + fee modified-EP + memetic value."""
    _guard_model(spec)
    _guard_emission_priced(spec["tokenomics"])

    network = _network_value(spec["tokenomics"], spec["onchain"], spec.get("network", {}))
    ep = _modified_ep(spec)

    body = {
        "asset_id": spec.get("asset_id", "crypto-asset"),
        "as_of": spec.get("as_of", ""),
        "valuation_method": spec.get("valuation_method", "fee_modified_ep"),
        "network_value": network,
        "modified_economic_profit": ep,
    }

    memetic_spec = spec.get("memetic")
    if memetic_spec is not None:
        body["memetic_value"] = _memetic_value(memetic_spec)

    # Verdict: a fee-bearing chain with a finite modified-EP is scored; a positive
    # modified-EP is value-accretive after security + dilution + reflexive tail risk.
    if not math.isfinite(ep["modified_ep"]):
        raise CryptoValuationError("modified_ep is not finite")
    body["verdict"] = "accretive" if ep["modified_ep"] > 0 else "value_destroying"

    receipt = dict(body)
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def run_valuation(path: str) -> dict:
    """Load, schema-validate and evaluate a CryptoAssetValuation fixture."""
    validate_json_file(path, _SCHEMA)
    spec = json.loads(Path(path).read_text())
    return evaluate_valuation(spec)
