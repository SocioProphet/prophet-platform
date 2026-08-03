"""BehavioralRegime contract (BR-1) -- greed/fear regimes + prospect theory.

Crypto returns are psychology-driven and regime-switching: a "greed" (euphoria)
regime with a high mean AND high volatility, and a "fear" (capitulation) regime with
a low/negative mean and lower volatility. This contract fits a 2-state Hamilton-style
Markov regime-switching model and overlays a prospect-theory value distortion.

Markov regime switching (Hamilton)
----------------------------------
A 2x2 transition matrix ``P`` (rows == P(next | current), each row summing to 1) and
per-regime Gaussian return distributions. Given a return series, a forward Hamilton
filter produces the posterior P(greed) at each step; a point is labelled greed when
that posterior exceeds 0.5. Teeth: a transition matrix whose rows do not sum to 1 is
REJECTED; and on a seeded greed-heavy series the greed-labelled points must exhibit a
HIGHER mean AND a HIGHER volatility than the fear-labelled points.

Prospect theory (Kahneman-Tversky)
----------------------------------
Value function ``v(x) = x^alpha`` for gains and ``v(x) = -lambda*(-x)^beta`` for
losses (loss aversion ``lambda > 1``), and probability weighting
``w(p) = p^gamma / (p^gamma + (1-p)^gamma)^(1/gamma)``. Teeth: ``lambda <= 1`` is
REJECTED (there must be loss aversion), and a probability weighting that is not
monotone increasing over [0,1] is REJECTED.

Memory-regime binding (consume by reference)
--------------------------------------------
Each regime carries an ``arrival_regime`` label drawn from the memory-mesh regime
characterizer's taxonomy: the reflexive / self-exciting phase is the
``hawkes_self_exciting`` (or ``long_memory``) arrival regime -- the SAME taxonomy the
memory mesh uses -- rather than a private label. The reflexive fat-tailed F consumed
by CAV-1 corresponds to this self-exciting arrival regime.

Deterministic and stdlib-only (seeded). Measurement, simulation and audit only.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from ..settlement import _canonical, _sha256
from ..validation import validate_json_file

_SCHEMA = "schemas/behavioral_regime.schema.json"

# The memory-mesh regime characterizer taxonomy (consumed by reference).
ARRIVAL_REGIMES = {"poisson_memoryless", "hawkes_self_exciting", "long_memory"}

_ROW_SUM_TOL = 1e-9


class BehavioralRegimeError(ValueError):
    """Raised when a regime spec is inadmissible (REJECTED)."""


# --------------------------------------------------------------------------- #
# transition matrix
# --------------------------------------------------------------------------- #
def _validate_transition_matrix(P: list) -> list:
    """A 2x2 stochastic matrix; each row must sum to 1 (teeth)."""
    if len(P) != 2 or any(len(row) != 2 for row in P):
        raise BehavioralRegimeError("transition_matrix must be 2x2 (greed, fear)")
    rows = [[float(x) for x in row] for row in P]
    for i, row in enumerate(rows):
        if any(x < 0 for x in row):
            raise BehavioralRegimeError(f"transition_matrix row {i} has a negative probability")
        if not math.isclose(sum(row), 1.0, abs_tol=_ROW_SUM_TOL):
            raise BehavioralRegimeError(
                f"REJECTED: transition_matrix row {i} sums to {sum(row)}, not 1.0; "
                "a regime-switching transition matrix must be row-stochastic"
            )
    return rows


# --------------------------------------------------------------------------- #
# prospect theory
# --------------------------------------------------------------------------- #
def prospect_value(x: float, alpha: float, beta: float, lam: float) -> float:
    """KT value function: gains x^alpha; losses -lambda*(-x)^beta (lambda>1)."""
    if x >= 0:
        return x ** alpha
    return -lam * ((-x) ** beta)


def probability_weight(p: float, gamma: float) -> float:
    """Tversky-Kahneman probability weighting w(p)."""
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    num = p ** gamma
    den = (p ** gamma + (1.0 - p) ** gamma) ** (1.0 / gamma)
    return num / den


def _validate_prospect(params: dict) -> dict:
    """Teeth: loss aversion lambda>1, and monotone-increasing probability weighting."""
    alpha = float(params.get("alpha", 0.88))
    beta = float(params.get("beta", 0.88))
    lam = float(params.get("lambda", 2.25))
    gamma = float(params.get("gamma", 0.61))

    if lam <= 1.0:
        raise BehavioralRegimeError(
            f"REJECTED: prospect-theory loss aversion lambda={lam} <= 1; "
            "loss aversion requires lambda > 1"
        )
    # Numerically verify probability weighting is monotone non-decreasing on [0,1].
    grid = [i / 200.0 for i in range(201)]
    w = [probability_weight(p, gamma) for p in grid]
    for i in range(len(w) - 1):
        if w[i + 1] < w[i] - 1e-9:
            raise BehavioralRegimeError(
                f"REJECTED: probability weighting is non-monotone at p~{grid[i]:.3f} "
                f"(gamma={gamma}); a weighting function must be monotone increasing"
            )
    # A representative distortion: loss aversion ratio at unit stake.
    loss_aversion_ratio = -prospect_value(-1.0, alpha, beta, lam) / prospect_value(1.0, alpha, beta, lam)
    return {
        "alpha": alpha,
        "beta": beta,
        "lambda": lam,
        "gamma": gamma,
        "loss_aversion_ratio": loss_aversion_ratio,
        "w_at_0_1": probability_weight(0.1, gamma),
        "w_at_0_9": probability_weight(0.9, gamma),
        "monotone_weighting": True,
    }


# --------------------------------------------------------------------------- #
# simulation + Hamilton filter
# --------------------------------------------------------------------------- #
_GREED, _FEAR = 0, 1


def _gauss_pdf(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2.0 * math.pi))


def _simulate_series(P: list, regimes: dict, n: int, seed: int) -> list:
    """Simulate a return series from the regime-switching model (seeded)."""
    rng = random.Random(seed)
    mu = [regimes["greed"]["mu"], regimes["fear"]["mu"]]
    sigma = [regimes["greed"]["sigma"], regimes["fear"]["sigma"]]
    state = _GREED if rng.random() < 0.5 else _FEAR
    out = []
    for _ in range(n):
        r = rng.gauss(mu[state], sigma[state])
        out.append(r)
        state = _GREED if rng.random() < P[state][_GREED] else _FEAR
    return out


def hamilton_filter(series: list, P: list, regimes: dict) -> list:
    """Forward Hamilton filter -> posterior P(greed) at each step."""
    mu = [regimes["greed"]["mu"], regimes["fear"]["mu"]]
    sigma = [regimes["greed"]["sigma"], regimes["fear"]["sigma"]]
    xi = [0.5, 0.5]  # prior over (greed, fear)
    posterior = []
    for r in series:
        # predict: propagate through P (columns are next-state)
        pred = [
            xi[_GREED] * P[_GREED][j] + xi[_FEAR] * P[_FEAR][j] for j in (_GREED, _FEAR)
        ]
        # update with Gaussian emission density
        dens = [_gauss_pdf(r, mu[j], sigma[j]) for j in (_GREED, _FEAR)]
        unnorm = [pred[j] * dens[j] for j in (_GREED, _FEAR)]
        total = sum(unnorm)
        if total <= 0:
            xi = [0.5, 0.5]
        else:
            xi = [u / total for u in unnorm]
        posterior.append(xi[_GREED])
    return posterior


def _classify_and_stat(series: list, posterior: list) -> dict:
    greed = [r for r, pg in zip(series, posterior) if pg > 0.5]
    fear = [r for r, pg in zip(series, posterior) if pg <= 0.5]

    def _mean(xs):
        return sum(xs) / len(xs) if xs else float("nan")

    def _vol(xs):
        if len(xs) < 2:
            return float("nan")
        m = _mean(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

    greed_mean, fear_mean = _mean(greed), _mean(fear)
    greed_vol, fear_vol = _vol(greed), _vol(fear)
    return {
        "n_total": len(series),
        "n_greed": len(greed),
        "n_fear": len(fear),
        "greed_mean": greed_mean,
        "fear_mean": fear_mean,
        "greed_vol": greed_vol,
        "fear_vol": fear_vol,
        "greed_has_higher_mean": bool(greed_mean > fear_mean),
        "greed_has_higher_vol": bool(greed_vol > fear_vol),
    }


# --------------------------------------------------------------------------- #
# contract
# --------------------------------------------------------------------------- #
def evaluate_behavioral_regime(spec: dict) -> dict:
    """Evaluate BR-1: validate matrix + prospect params, classify a series, receipt."""
    P = _validate_transition_matrix(spec["transition_matrix"])
    regimes = spec["regimes"]
    for name in ("greed", "fear"):
        if name not in regimes:
            raise BehavioralRegimeError(f"regimes must define '{name}'")

    arrival_regime = spec.get("arrival_regime", "hawkes_self_exciting")
    if arrival_regime not in ARRIVAL_REGIMES:
        raise BehavioralRegimeError(
            f"unknown arrival_regime {arrival_regime!r}; the memory-mesh characterizer "
            f"taxonomy is {sorted(ARRIVAL_REGIMES)}"
        )

    prospect = _validate_prospect(spec.get("prospect_theory", {}))

    # Series: either provided directly or simulated (seeded) from the model.
    if "series" in spec:
        series = [float(x) for x in spec["series"]]
        source = "provided"
    else:
        sim = spec.get("simulate", {})
        series = _simulate_series(
            P, regimes, n=int(sim.get("n", 400)), seed=int(sim.get("seed", 0))
        )
        source = f"simulated(seed={int(sim.get('seed', 0))})"
    posterior = hamilton_filter(series, P, regimes)
    stats = _classify_and_stat(series, posterior)

    body = {
        "contract_id": spec.get("contract_id", "behavioral-regime"),
        "as_of": spec.get("as_of", ""),
        "arrival_regime": arrival_regime,
        "memory_regime_ref": spec.get(
            "memory_regime_ref",
            "memory-mesh:characterizer/arrival-regime",
        ),
        "transition_matrix": P,
        "regime_stats": stats,
        "prospect_theory": prospect,
        "series_source": source,
        "verdict": "verified"
        if (stats["greed_has_higher_mean"] and stats["greed_has_higher_vol"])
        else "regime_separation_weak",
    }
    receipt = dict(body)
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def run_behavioral_regime(path: str) -> dict:
    """Load, schema-validate and evaluate a BehavioralRegime fixture."""
    validate_json_file(path, _SCHEMA)
    spec = json.loads(Path(path).read_text())
    return evaluate_behavioral_regime(spec)
