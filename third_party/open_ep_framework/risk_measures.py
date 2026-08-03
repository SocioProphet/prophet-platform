"""Unified risk-measure family over a fitted/simulated loss distribution F (RM-1).

Every risk measure this module exposes is derived from ONE interface —
``risk(F, kernel, reference, horizon, ...)`` — evaluated over the SAME loss
distribution ``F``. There is no per-measure toggle with divergent plumbing: a
Sharpe ratio, a Sortino ratio, a Kappa_n, a VaR, an Expected Shortfall and a
spectral measure are all *lenses on the same F*, so results reconcile.

Two families, one distribution
------------------------------
Reward-to-risk (a return divided by a dispersion functional of F):
  * ``sharpe``   -- denominator = standard deviation (two-sided; NON-coherent).
  * ``sortino``  -- denominator = downside deviation sqrt(LPM_2(MAR));
                    penalizes only returns below the Minimum Acceptable Return.
  * ``kappa``    -- (E[R]-tau) / LPM_n(tau)^(1/n), LPM_n(tau)=E[(tau-R)_+^n].
                    n generalizes the family: n=0 shortfall probability,
                    n=1 Omega-style, n=2 == Sortino, n>2 extreme-averse.

Tail / coherent (a capital magnitude on the loss side of F):
  * ``var``               -- VaR_alpha, the loss quantile. NON-coherent
                             (subadditivity can fail); flagged accordingly.
  * ``expected_shortfall``-- CVaR_alpha = E[loss | loss >= VaR_alpha]. Coherent.
  * ``spectral``          -- integral phi(p) VaR_p dp. Coherent iff phi is
                             non-increasing; ES is the flat-tail spectrum.

Distribution + horizon
----------------------
``F`` is a functional object, not a scalar. It can be supplied as raw samples or
simulated from credit inputs with a one-factor common shock
(PD_short = PD_long * (w1*systematic + w2*idiosyncratic)). Risk is evaluated over
a HORIZON via sqrt-time scaling, so ``risk_term_structure`` yields a term
structure across horizons rather than a single number; ``largest_cumulative_gap``
provides the LCR-style largest-cumulative-outflow gap over N days.

Teeth this module makes assertable
----------------------------------
  * Same F, many lenses reconcile (Sortino ignores upside where Sharpe does not).
  * ES_alpha >= VaR_alpha at the same alpha (a tail average dominates its quantile).
  * VaR / Sharpe report ``coherent == False`` (callers gate capital on this).
  * A distribution with n < 30 samples is flagged ``provisional`` (min-n >= 30).
  * Every measure fingerprints its distribution, so receipts are reproducible.

Deterministic and stdlib-only: analytic where possible, seeded PRNG otherwise,
so CI is reproducible.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field

MIN_SAMPLES = 30

REWARD_TO_RISK_KERNELS = {"sharpe", "sortino", "kappa"}
TAIL_KERNELS = {"var", "expected_shortfall", "spectral"}
DISPERSION_KERNELS = {"stddev"}
KNOWN_KERNELS = REWARD_TO_RISK_KERNELS | TAIL_KERNELS | DISPERSION_KERNELS

# Coherent tail measures are the only defensible default for RAROC economic
# capital. VaR, Sharpe's sigma and plain stddev are NOT coherent risk measures.
COHERENT_KERNELS = {"expected_shortfall", "spectral"}
NONCOHERENT_KERNELS = {"var", "stddev", "sharpe"}


class RiskMeasureError(ValueError):
    """Raised for an unusable measure request (unknown kernel, empty F, ...)."""


# --------------------------------------------------------------------------- #
# distribution F
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LossDistribution:
    """A distribution F of period returns R (positive == gain).

    ``losses`` is the loss side (-R). Tail measures read ``losses``;
    reward-to-risk measures read the return samples directly.
    """

    samples: tuple[float, ...]
    horizon_days: int = 1
    source: str = "samples"
    seed: int | None = None
    beta: float | None = None  # market beta for an equity/market return F

    def __post_init__(self) -> None:
        if not self.samples:
            raise RiskMeasureError("loss distribution F requires at least one sample")

    @property
    def n(self) -> int:
        return len(self.samples)

    @property
    def provisional(self) -> bool:
        """True when F is fitted on fewer than MIN_SAMPLES observations."""
        return self.n < MIN_SAMPLES

    @property
    def losses(self) -> tuple[float, ...]:
        return tuple(-r for r in self.samples)

    def fingerprint(self) -> str:
        """Reproducible id for the receipt (FIPS SHA-256 over canonical F)."""
        body = {
            "samples": [float(x) for x in self.samples],
            "horizon_days": self.horizon_days,
            "source": self.source,
            "seed": self.seed,
            "beta": self.beta,
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_samples(cls, samples, horizon_days: int = 1) -> "LossDistribution":
        return cls(tuple(float(x) for x in samples), horizon_days=horizon_days, source="samples")

    @classmethod
    def simulate_credit(
        cls,
        pd_long: float,
        lgd: float,
        ead: float,
        w_systematic: float,
        w_idiosyncratic: float,
        horizon_days: int = 1,
        n_scenarios: int = 1000,
        seed: int = 0,
    ) -> "LossDistribution":
        """Simulate a credit loss distribution under a one-factor common shock.

        Each scenario draws a systematic factor Z (shared) and an idiosyncratic
        factor e, combines them into a stressed short-horizon default rate
        ``PD_short = PD_long * (w1*systematic + w2*idiosyncratic)`` clamped to
        [0,1], and books a loss of ``PD_short * LGD * EAD``. Returns are stored
        as negative losses (a loss is a negative return). Seeded for CI.
        """
        rng = random.Random(seed)
        samples: list[float] = []
        for _ in range(n_scenarios):
            systematic = math.exp(rng.gauss(0.0, 1.0))
            idiosyncratic = math.exp(rng.gauss(0.0, 1.0))
            shock = w_systematic * systematic + w_idiosyncratic * idiosyncratic
            pd_short = min(1.0, max(0.0, pd_long * shock))
            loss = pd_short * lgd * ead
            samples.append(-loss)
        return cls(tuple(samples), horizon_days=horizon_days, source="credit_one_factor", seed=seed)

    @classmethod
    def simulate_equity(
        cls,
        mu: float,
        sigma: float,
        df: float = 4.0,
        beta: float | None = None,
        horizon_days: int = 1,
        n_scenarios: int = 1000,
        seed: int = 0,
    ) -> "LossDistribution":
        """Simulate a fat-tailed equity/market RETURN distribution F (Student-t).

        Equity is a return distribution (not a loss-only credit distribution): the
        SAME ``risk`` interface reads it for Sharpe / Sortino / drawdown / VaR / ES
        and a market ``beta`` can be carried for market-risk aggregation. Draws are
        Student-t with ``df`` degrees of freedom (df small == fat tails / long
        left tail), located at ``mu`` and scaled by ``sigma``. Seeded for CI.
        """
        rng = random.Random(seed)
        samples: list[float] = []
        for _ in range(n_scenarios):
            z = rng.gauss(0.0, 1.0)
            chi2 = sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(max(1, int(round(df)))))
            t = z / math.sqrt(chi2 / max(1, int(round(df)))) if chi2 > 0 else z
            samples.append(mu + sigma * t)
        return cls(tuple(samples), horizon_days=horizon_days, source="equity_student_t", seed=seed, beta=beta)


# --------------------------------------------------------------------------- #
# statistics
# --------------------------------------------------------------------------- #
def _mean(xs) -> float:
    return sum(xs) / len(xs)


def _stdev(xs) -> float:
    """Sample standard deviation (ddof=1); 0.0 for a degenerate single sample."""
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def lpm(samples, tau: float, order: int) -> float:
    """Lower partial moment LPM_n(tau) = E[(tau - R)_+^n] over F.

    order == 0 is the shortfall probability P[R < tau].
    """
    shortfalls = [tau - x for x in samples if x < tau]
    if order == 0:
        return len(shortfalls) / len(samples)
    return sum(s ** order for s in shortfalls) / len(samples)


def downside_deviation(samples, mar: float) -> float:
    """Downside deviation sqrt(LPM_2(MAR)) about a Minimum Acceptable Return."""
    return math.sqrt(lpm(samples, mar, 2))


def _central_moment(samples, order: int) -> float:
    m = _mean(samples)
    return sum((x - m) ** order for x in samples) / len(samples)


def skewness(samples) -> float:
    """Sample skewness m3 / m2^1.5 (0 for a symmetric F)."""
    m2 = _central_moment(samples, 2)
    if m2 <= 0:
        return 0.0
    return _central_moment(samples, 3) / (m2 ** 1.5)


def excess_kurtosis(samples) -> float:
    """Excess kurtosis m4 / m2^2 - 3 (0 for a Gaussian F; > 0 for fat tails)."""
    m2 = _central_moment(samples, 2)
    if m2 <= 0:
        return 0.0
    return _central_moment(samples, 4) / (m2 ** 2) - 3.0


# Thresholds above which lower-moment measures (Sharpe / normal-VaR) miss risk.
_SKEW_TOL = 0.2
_EXCESS_KURT_TOL = 0.5


def _higher_moment_warning(samples) -> str | None:
    sk = skewness(samples)
    ek = excess_kurtosis(samples)
    if abs(sk) > _SKEW_TOL or abs(ek) > _EXCESS_KURT_TOL:
        return (
            f"higher-moment risk unpriced (skew={sk:.3f}, excess_kurtosis={ek:.3f}); "
            "prefer Sortino / Expected Shortfall over Sharpe / normal-VaR"
        )
    return None


def _tail(losses, alpha: float):
    """Return (tail_losses, var_threshold) for confidence ``alpha``.

    The tail is the worst ``k = ceil((1-alpha) * n)`` losses. VaR_alpha is the
    smallest loss in that tail (the quantile); ES_alpha is the tail mean. By
    construction ES_alpha >= VaR_alpha for every F.
    """
    n = len(losses)
    ordered = sorted(losses)
    k = max(1, math.ceil((1.0 - alpha) * n))
    tail = ordered[n - k:]
    return tail, min(tail)


# --------------------------------------------------------------------------- #
# result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RiskMeasure:
    kernel: str
    family: str  # "dispersion" | "reward_to_risk" | "tail"
    value: float  # ratio for reward-to-risk; capital magnitude for tail/dispersion
    risk_functional: float  # the dispersion/capital denominator used
    coherent: bool
    reference: float
    alpha: float | None
    order: int | None
    horizon: float
    n_samples: int
    provisional: bool
    distribution_id: str
    downside_only: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def summary(self) -> dict:
        """Compact, receipt-ready record of the measure and its distribution."""
        return {
            "kernel": self.kernel,
            "family": self.family,
            "value": self.value,
            "risk_functional": self.risk_functional,
            "coherent": self.coherent,
            "downside_only": self.downside_only,
            "reference": self.reference,
            "alpha": self.alpha,
            "order": self.order,
            "horizon": self.horizon,
            "n_samples": self.n_samples,
            "provisional": self.provisional,
            "distribution_id": self.distribution_id,
            "warnings": list(self.warnings),
        }


# --------------------------------------------------------------------------- #
# the single interface
# --------------------------------------------------------------------------- #
def risk(
    F: LossDistribution,
    kernel: str,
    *,
    reference: float = 0.0,
    horizon: float = 1.0,
    alpha: float = 0.95,
    order: int = 2,
    phi=None,
) -> RiskMeasure:
    """Evaluate one risk lens ``kernel`` over the loss distribution ``F``.

    ``reference`` is the MAR / risk-free hurdle for reward-to-risk kernels.
    ``horizon`` scales magnitudes by sqrt-time (a term-structure point).
    ``alpha`` is the tail confidence; ``order`` the Kappa/LPM moment; ``phi`` an
    optional spectral weight vector over the tail (non-increasing == coherent).
    """
    if kernel not in KNOWN_KERNELS:
        raise RiskMeasureError(
            f"unknown risk kernel {kernel!r}; known: {sorted(KNOWN_KERNELS)}"
        )
    if horizon <= 0:
        raise RiskMeasureError("horizon must be positive")

    r = list(F.samples)
    n = len(r)
    m = _mean(r)
    hscale = math.sqrt(horizon)
    warnings: list[str] = []
    if F.provisional:
        warnings.append(
            f"distribution fitted on n={n} < {MIN_SAMPLES}; risk estimate is provisional"
        )

    def _rm(**kw) -> RiskMeasure:
        return RiskMeasure(
            kernel=kernel,
            reference=reference,
            horizon=horizon,
            n_samples=n,
            provisional=F.provisional,
            distribution_id=F.fingerprint(),
            warnings=tuple(warnings),
            **kw,
        )

    # -- dispersion ------------------------------------------------------- #
    if kernel == "stddev":
        sd = _stdev(r) * hscale
        return _rm(family="dispersion", value=sd, risk_functional=sd,
                   coherent=False, alpha=None, order=None)

    # -- reward-to-risk --------------------------------------------------- #
    if kernel == "sharpe":
        warnings.append("Sharpe uses two-sided sigma; it is not a coherent risk measure and penalizes upside")
        hm = _higher_moment_warning(r)
        if hm:
            warnings.append(hm)
        denom = _stdev(r) * hscale
        ratio = (m - reference) * horizon / denom if denom > 0 else math.inf
        return _rm(family="reward_to_risk", value=ratio, risk_functional=denom,
                   coherent=False, alpha=None, order=None)

    if kernel == "sortino":
        denom = downside_deviation(r, reference) * hscale
        ratio = (m - reference) * horizon / denom if denom > 0 else math.inf
        return _rm(family="reward_to_risk", value=ratio, risk_functional=denom,
                   coherent=False, alpha=None, order=2, downside_only=True)

    if kernel == "kappa":
        if order < 0:
            raise RiskMeasureError("kappa order must be >= 0")
        moment = lpm(r, reference, order)
        if order == 0:
            denom = moment  # shortfall probability
        else:
            denom = moment ** (1.0 / order)
        denom *= hscale
        ratio = (m - reference) * horizon / denom if denom > 0 else math.inf
        return _rm(family="reward_to_risk", value=ratio, risk_functional=denom,
                   coherent=False, alpha=None, order=order, downside_only=True)

    # -- tail / coherent -------------------------------------------------- #
    losses = list(F.losses)
    tail, var_threshold = _tail(losses, alpha)

    if kernel == "var":
        warnings.append(
            "VaR is not subadditive; it can violate coherence and understate diversified tail risk"
        )
        hm = _higher_moment_warning(r)
        if hm:
            warnings.append(hm)
        value = var_threshold * hscale
        return _rm(family="tail", value=value, risk_functional=value,
                   coherent=False, alpha=alpha, order=None)

    if kernel == "expected_shortfall":
        value = _mean(tail) * hscale
        return _rm(family="tail", value=value, risk_functional=value,
                   coherent=True, alpha=alpha, order=None)

    # spectral
    ordered_tail = sorted(tail, reverse=True)  # worst first
    if phi is None:
        # flat tail spectrum == Expected Shortfall (coherent by construction)
        value = _mean(ordered_tail) * hscale
        return _rm(family="tail", value=value, risk_functional=value,
                   coherent=True, alpha=alpha, order=None)
    weights = [float(w) for w in phi]
    if len(weights) != len(ordered_tail):
        raise RiskMeasureError(
            f"spectral phi has {len(weights)} weights but tail has {len(ordered_tail)} points"
        )
    total = sum(weights)
    if total <= 0:
        raise RiskMeasureError("spectral phi weights must sum to a positive value")
    weights = [w / total for w in weights]
    non_increasing = all(weights[i] >= weights[i + 1] - 1e-12 for i in range(len(weights) - 1))
    if not non_increasing:
        warnings.append("spectral phi is not non-increasing; the resulting measure is not coherent")
    value = sum(w * loss for w, loss in zip(weights, ordered_tail)) * hscale
    return _rm(family="tail", value=value, risk_functional=value,
               coherent=non_increasing, alpha=alpha, order=None)


def is_coherent(kernel: str) -> bool:
    """Whether ``kernel`` is a coherent risk measure by default (phi flat)."""
    return kernel in COHERENT_KERNELS


def risk_term_structure(
    F: LossDistribution,
    kernel: str,
    horizons,
    **kwargs,
) -> dict:
    """Risk as a term structure across horizons (not a scalar).

    Returns ``{horizon: measure_value}`` for each requested horizon.
    """
    return {float(h): risk(F, kernel, horizon=float(h), **kwargs).value for h in horizons}


def largest_cumulative_gap(daily_net_flows) -> float:
    """LCR-style largest cumulative net-outflow gap over N days.

    ``daily_net_flows`` are signed (positive == inflow). Returns the magnitude of
    the deepest cumulative shortfall (>= 0); this is the horizon liquidity risk a
    coherent capital buffer must cover.
    """
    cumulative = 0.0
    worst = 0.0
    for flow in daily_net_flows:
        cumulative += float(flow)
        worst = min(worst, cumulative)
    return -worst


def max_drawdown(returns) -> float:
    """Path-dependent maximum drawdown of a return series (equity/market risk)."""
    peak = 1.0
    equity = 1.0
    mdd = 0.0
    for r in returns:
        equity *= (1.0 + float(r))
        peak = max(peak, equity)
        if peak > 0:
            mdd = max(mdd, (peak - equity) / peak)
    return mdd


# --------------------------------------------------------------------------- #
# structure / issuance: a tranche F is a transform of the pool F
# --------------------------------------------------------------------------- #
def structural_transform(F_pool: LossDistribution, attach: float, detach: float) -> LossDistribution:
    """Securitization waterfall: derive a tranche loss distribution from the pool.

    A [attach, detach] tranche absorbs pool loss between its attach and detach
    points: ``tranche_loss = clip(pool_loss - attach, 0, detach - attach)``. Equity
    is simply the most-junior (first-loss) tranche of the same waterfall. Because a
    contiguous partition of [0, cap] sums back to the pool loss on every scenario,
    the tranche expected losses reconcile to the pool EL (conservation).

    A tranche with ``detach <= attach`` is REJECTED.
    """
    if detach <= attach:
        raise RiskMeasureError(
            f"tranche detach ({detach}) must exceed attach ({attach})"
        )
    width = detach - attach
    tranche_samples = tuple(
        -min(max(loss - attach, 0.0), width) for loss in F_pool.losses
    )
    return LossDistribution(
        tranche_samples,
        horizon_days=F_pool.horizon_days,
        source=f"tranche[{attach},{detach}]",
        seed=F_pool.seed,
    )


def expected_loss(F: LossDistribution) -> float:
    """Expected loss EL = E[loss] over F (mean of the loss side)."""
    return _mean(F.losses)


# --------------------------------------------------------------------------- #
# coherent allocation: Euler/marginal component capital
# --------------------------------------------------------------------------- #
def euler_allocation(
    components: dict,
    kernel: str = "expected_shortfall",
    *,
    alpha: float = 0.95,
    horizon: float = 1.0,
    allow_noncoherent: bool = False,
) -> dict:
    """Euler (marginal) capital allocation of a coherent measure to components.

    ``components`` maps a node name to that node's ``LossDistribution``, aligned
    scenario-by-scenario (same length, same draws). The portfolio loss per scenario
    is the sum of component losses. For a COHERENT measure the Euler contribution of
    component i is ``E[loss_i | portfolio_loss in tail]``; because conditional
    expectation is linear, the contributions SUM to the portfolio total exactly --
    the same sum-to-total conservation the IC-1 settlement enforces. This is what
    lets EconomicCapital aggregate up and allocate down an arbitrary hierarchy cut.

    A NON-coherent measure (VaR) cannot be cleanly Euler-allocated (it is not
    subadditive); this requires ``allow_noncoherent=True`` and emits a warning.
    """
    if kernel not in KNOWN_KERNELS:
        raise RiskMeasureError(f"unknown risk kernel {kernel!r}")
    if not components:
        raise RiskMeasureError("euler_allocation requires at least one component")

    names = list(components)
    loss_columns = {name: list(components[name].losses) for name in names}
    n = len(loss_columns[names[0]])
    if any(len(col) != n for col in loss_columns.values()):
        raise RiskMeasureError("component distributions must be scenario-aligned (equal length)")

    warnings: list[str] = []
    coherent = kernel in COHERENT_KERNELS
    if not coherent:
        warnings.append(
            f"incoherence warning: '{kernel}' is not subadditive; Euler/marginal allocation "
            "is not well defined and contributions need not sum to the total"
        )
        if not allow_noncoherent:
            raise RiskMeasureError(
                f"REJECTED: cannot Euler-allocate non-coherent measure '{kernel}' "
                "without allow_noncoherent override"
            )

    portfolio_losses = [sum(loss_columns[name][s] for name in names) for s in range(n)]
    order = sorted(range(n), key=lambda s: portfolio_losses[s])
    k = max(1, math.ceil((1.0 - alpha) * n))
    tail_idx = order[n - k:]
    hscale = math.sqrt(horizon)

    contributions = {
        name: (sum(loss_columns[name][s] for s in tail_idx) / k) * hscale for name in names
    }
    total = (sum(portfolio_losses[s] for s in tail_idx) / k) * hscale
    sum_contrib = sum(contributions.values())
    return {
        "kernel": kernel,
        "alpha": alpha,
        "horizon": horizon,
        "coherent": coherent,
        "total": total,
        "contributions": contributions,
        "sum_of_contributions": sum_contrib,
        "sum_to_total": math.isclose(sum_contrib, total, rel_tol=1e-9, abs_tol=1e-9),
        "warnings": warnings,
    }
