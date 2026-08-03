"""Aggregation-methodology taxonomy with the tail-dependence guard (AGG-1).

Rolling three risk-type economic capitals (credit / market / operational) into ONE
number is a MODELLING CHOICE, and the choice determines how much diversification you
are allowed to claim. This contract makes the choice EXPLICIT, receipted and governed,
with its stated trade-off and its limitation, and it guards the one failure that
matters: assuming diversification that evaporates in the tail (the 2008 lesson).

The taxonomy (trade-off / limitation)
-------------------------------------
  * summation             -- Sigma EC_i. Conservative super-additive UPPER BOUND;
                             ignores diversification entirely.
  * constant_diversification -- Sigma EC_i x (1 - d). Simple; the flat haircut d is
                             not risk-sensitive and is essentially arbitrary.
  * variance_covariance   -- sqrt(EC' R EC). Bilateral (linear) correlation; MISSES
                             non-linearity and tail dependence.
  * copula                -- joins the marginals with a dependence structure that has
                             UPPER-TAIL DEPENDENCE; captures the tail, but is hard to
                             validate (model risk).
  * full_simulation       -- the full joint loss distribution; flexible, but carries
                             false-precision risk.

Summation is the conservative bound every other method is measured against.

Consume, do NOT reinvent
------------------------
  * ``regulatory_capital.economic_vs_regulatory`` (economic-prophet #42) applies a
    flat cross-risk diversification benefit -- this contract is the taxonomy that
    names WHICH aggregation produced that benefit and whether it survives the tail.
  * ``settlement`` (IC-1, #39) -- the FIPS SHA-256 ``sha256:`` receipt spine.
  * ``sociosphere:gbrg/governance/omnirisk_allocation.py`` (OMNI-1) -- soft ref; the
    aggregate EC is the cross-cut total the walker reconciles to per-node contributions.

Deterministic: the copula / full-simulation paths are SEEDED Monte-Carlo (stdlib
``random``), so CI is reproducible.

Teeth (verdicts)
----------------
  * VERIFIED -- the chosen method declares its assumption, records its limitation, and
        its aggregate is <= summation.
  * FLAGGED  -- a variance_covariance choice whose aggregate is BELOW a tail-dependent
        copula / simulation aggregate (it claims diversification that vanishes in the
        tail -- the 2008 lesson).
  * REJECTED (raises) --
        a method whose aggregate EXCEEDS summation (super-additive -- impossible for a
            legitimate diversification claim);
        a diversifying method (constant_diversification / variance_covariance / copula /
            full_simulation) with NO declared correlation / copula / diversification
            assumption (no silent diversification).

Measurement, simulation and audit only.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from .settlement import _canonical, _sha256
from .validation import validate_json_file

_SCHEMA = "schemas/aggregation_method.schema.json"
_TOL = 1e-6

OMNIRISK_WALKER_REF = "sociosphere:gbrg/governance/omnirisk_allocation.py (OMNI-1)"
REGCAP_REF = "economic-prophet:src/open_ep_framework/regulatory_capital.py#economic_vs_regulatory"

RISK_TYPES = ("credit", "market", "operational")
DIVERSIFYING_METHODS = frozenset(
    {"constant_diversification", "variance_covariance", "copula", "full_simulation"}
)
_TAIL_DEPENDENT = frozenset({"copula"})

TRADE_OFFS = {
    "summation": {
        "trade_off": "conservative super-additive upper bound",
        "limitation": "ignores diversification entirely",
    },
    "constant_diversification": {
        "trade_off": "single flat diversification haircut",
        "limitation": "not risk-sensitive; the haircut is arbitrary",
    },
    "variance_covariance": {
        "trade_off": "bilateral (linear) correlation",
        "limitation": "misses non-linearity and tail dependence",
    },
    "copula": {
        "trade_off": "captures tail dependence",
        "limitation": "hard to validate (model risk)",
    },
    "full_simulation": {
        "trade_off": "full joint loss distribution",
        "limitation": "false-precision risk",
    },
}


class AggregationMethodError(ValueError):
    """Raised when the aggregation choice violates the taxonomy teeth (REJECTED)."""


# --------------------------------------------------------------------------- #
# analytic methods
# --------------------------------------------------------------------------- #
def _correlation_matrix(corr: dict) -> list[list[float]]:
    cm = float(corr.get("credit_market", 0.0))
    co = float(corr.get("credit_operational", 0.0))
    mo = float(corr.get("market_operational", 0.0))
    return [[1.0, cm, co], [cm, 1.0, mo], [co, mo, 1.0]]


def _summation(ec: list[float]) -> float:
    return sum(ec)


def _constant_diversification(ec: list[float], d: float) -> float:
    return sum(ec) * (1.0 - d)


def _variance_covariance(ec: list[float], R: list[list[float]]) -> float:
    total = 0.0
    for i in range(len(ec)):
        for j in range(len(ec)):
            total += R[i][j] * ec[i] * ec[j]
    return math.sqrt(max(0.0, total))


# --------------------------------------------------------------------------- #
# simulated methods (seeded, deterministic)
# --------------------------------------------------------------------------- #
def _cholesky(R: list[list[float]]) -> list[list[float]]:
    n = len(R)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(1e-12, R[i][i] - s))
            else:
                L[i][j] = (R[i][j] - s) / L[j][j]
    return L


def _simulate_aggregate(
    ec: list[float], R: list[list[float]], confidence: float,
    *, seed: int, sims: int,
) -> float:
    """full_simulation: the `confidence` quantile of the summed joint loss under a
    Gaussian copula, by seeded Monte-Carlo.

    Lognormal marginals are each calibrated (from a seeded calibration batch) so their own
    `confidence` quantile equals the standalone ``EC_i``; positions are joined by a
    Gaussian copula (correlation ``R``). Because the marginals are skewed but light-tailed
    and the copula has no tail dependence, the simulated aggregate tracks the
    variance-covariance number -- which is exactly the point: full simulation buys
    precision, not a different diversification story (false-precision risk). Seeded, so CI
    is reproducible.
    """
    L = _cholesky(R)
    n = len(ec)
    sigma = 0.35  # marginal log-volatility (skew without heavy tails)

    def _draw(rng):
        z = [rng.gauss(0.0, 1.0) for _ in range(n)]
        corr = [sum(L[i][k] * z[k] for k in range(n)) for i in range(n)]
        return [math.exp(sigma * c) for c in corr]

    # Per-marginal calibration quantile q_i of exp(sigma * Z_i).
    cal_rng = random.Random(seed ^ 0x5DEECE66D)
    cal_cols = [[] for _ in range(n)]
    for _ in range(sims):
        d = _draw(cal_rng)
        for i in range(n):
            cal_cols[i].append(d[i])
    q = []
    for i in range(n):
        cal_cols[i].sort()
        q.append(cal_cols[i][min(sims - 1, int(round(confidence * sims)))])

    rng = random.Random(seed)
    agg = []
    for _ in range(sims):
        d = _draw(rng)
        agg.append(sum(ec[i] * d[i] / q[i] for i in range(n)))
    agg.sort()
    return agg[min(len(agg) - 1, int(round(confidence * len(agg))))]


# --------------------------------------------------------------------------- #
# comparison table over all computable methods
# --------------------------------------------------------------------------- #
def _compute_methods(ec: list[float], assumption: dict, confidence: float) -> dict:
    R = _correlation_matrix(assumption["correlation"]) if assumption.get("correlation") else None
    seed = int(assumption.get("seed", 7))
    sims = int(assumption.get("sims", 20000))

    methods: dict[str, float] = {"summation": _summation(ec)}
    if assumption.get("diversification_factor") is not None:
        methods["constant_diversification"] = _constant_diversification(
            ec, float(assumption["diversification_factor"])
        )
    if R is not None:
        vc = _variance_covariance(ec, R)
        methods["variance_covariance"] = vc
        # full_simulation = seeded Gaussian-copula Monte-Carlo (tracks the sqrt formula).
        methods["full_simulation"] = _simulate_aggregate(
            ec, R, confidence, seed=seed, sims=sims
        )
        # copula = tail-dependent aggregation: the declared upper-tail dependence lambda
        # pulls the aggregate from the correlation-diversified number (lambda=0) toward the
        # comonotone summation bound (lambda=1). Diversification vanishes in the tail.
        if assumption.get("tail_dependence") is not None or assumption.get("copula_family"):
            lam = float(assumption.get("tail_dependence", 0.0))
            lam = min(1.0, max(0.0, lam))
            methods["copula"] = vc + lam * (methods["summation"] - vc)
    return methods


# --------------------------------------------------------------------------- #
# contract
# --------------------------------------------------------------------------- #
def evaluate_contract(spec: dict) -> dict:
    contract_id = spec.get("contract_id", "agg")
    as_of = spec.get("as_of", "")
    method = spec["chosen_method"]
    confidence = float(spec.get("confidence", 0.999))
    assumption = spec.get("assumption") or {}
    ec = [float(spec["risk_inputs"][t]) for t in RISK_TYPES]

    # Teeth: a diversifying method must declare its assumption (no silent diversification).
    if method in DIVERSIFYING_METHODS:
        has_assumption = (
            (method == "constant_diversification" and assumption.get("diversification_factor") is not None)
            or (method in ("variance_covariance", "full_simulation") and assumption.get("correlation"))
            or (method == "copula" and assumption.get("correlation") and (
                assumption.get("copula_family") or assumption.get("tail_dependence") is not None))
        )
        if not has_assumption:
            raise AggregationMethodError(
                f"REJECTED: method {method!r} claims diversification but declares no "
                "correlation / copula / diversification assumption (no silent diversification)"
            )

    methods = _compute_methods(ec, assumption, confidence)
    summation = methods["summation"]
    if method not in methods:
        raise AggregationMethodError(
            f"REJECTED: chosen method {method!r} could not be computed from the declared "
            "assumption (missing correlation/copula parameters)"
        )
    chosen_aggregate = methods[method]

    warnings: list[str] = []

    # Teeth: no method may exceed the summation upper bound (super-additive).
    for name, value in methods.items():
        if value > summation + _TOL:
            raise AggregationMethodError(
                f"REJECTED: method {name!r} aggregate {value} exceeds the summation upper "
                f"bound {summation}; summation is the conservative super-additive ceiling"
            )

    # Teeth: variance_covariance understating a tail-dependent method is FLAGGED.
    flagged = False
    if method == "variance_covariance":
        for td in _TAIL_DEPENDENT:
            if td in methods and chosen_aggregate < methods[td] - _TOL:
                flagged = True
                warnings.append(
                    f"tail-dependence-blind: variance_covariance aggregate {chosen_aggregate:.2f} "
                    f"is below the {td} aggregate {methods[td]:.2f}; the claimed diversification "
                    "vanishes in the tail (the 2008 lesson)"
                )

    diversification_benefit = summation - chosen_aggregate
    verdict = "flagged" if flagged else "verified"

    body = {
        "contract_id": contract_id,
        "as_of": as_of,
        "chosen_method": method,
        "confidence": confidence,
        "risk_inputs": {t: ec[i] for i, t in enumerate(RISK_TYPES)},
        "chosen_aggregate": chosen_aggregate,
        "summation_upper_bound": summation,
        "diversification_benefit": diversification_benefit,
        "diversification_benefit_pct": (diversification_benefit / summation * 100) if summation else 0.0,
        "method_comparison": methods,
        "trade_off": TRADE_OFFS[method]["trade_off"],
        "stated_limitation": spec.get("limitation", TRADE_OFFS[method]["limitation"]),
        "assumption": assumption,
        "verdict": verdict,
        "soft_references": {
            "economic_vs_regulatory": REGCAP_REF,
            "omnirisk_walker": OMNIRISK_WALKER_REF,
        },
        "warnings": warnings,
    }
    receipt = dict(body)
    receipt["input_hash"] = _sha256(_canonical(spec))
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def run_aggregation_method(path: str) -> dict:
    """Load, schema-validate and evaluate an AggregationMethod contract fixture."""
    validate_json_file(path, _SCHEMA)
    spec = json.loads(Path(path).read_text())
    return evaluate_contract(spec)
