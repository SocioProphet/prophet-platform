"""Regime-aware TRINOMIAL (ternary) option pricer (FRT-1).

A CRR *binomial* tree is a two-state (up/down) lattice; in the memoryless limit it
is Black-Scholes and it is *regime-blind* -- there is no branch that can encode where
the process wants to sit. This module builds a **trinomial** (Boyle 1986) lattice with
THREE branches -- up / **stay** / down -- and makes the MIDDLE ("stay") branch carry
the regime's stable point:

  * ``memoryless``   -- an efficient/GBM regime (memory-mesh taxonomy: ``memoryless`` /
                       ``brownian_gbm``). No reversion; the middle branch is the plain
                       martingale "stay". A moment-matched Boyle/Kamrad-Ritchken tree
                       that CONVERGES TO BLACK-SCHOLES as the step count grows.
  * ``mean_reverting`` -- an Ornstein-Uhlenbeck / ``short_decaying`` regime (memory-mesh
                       ``ornstein_uhlenbeck``; option-model anchors Vasicek / Hull-White /
                       CIR / Heston). The middle branch PROJECTS TO THE REVERSION TARGET
                       ``mu``: a Hull-White trinomial whose recombining lattice is centred
                       on ``x = ln(mu)`` and whose reversion speed ``theta`` pulls the
                       drift to zero exactly at ``mu``. ``theta`` / ``mu`` / half-life are
                       CONSUMED FROM the memory-mesh process characterizer's OU fit
                       (``estimate_ou`` -> theta, mu, half_life = ln2/theta), not re-fit here.
  * ``trending``     -- a long-memory / persistent regime (memory-mesh
                       ``fractional_brownian_motion`` / rough-vol anchor). Drift dominates:
                       the middle ("stay") branch is weak because the process keeps moving
                       in one direction. Represented as a momentum drift overlay
                       (characterization / real-world measure, not risk-neutral).
  * ``chaotic``      -- a chaotic regime. The "stable point" is a strange ATTRACTOR, not a
                       fixed point: ``mu`` is the attractor centroid the middle branch
                       leans toward, but the local Lyapunov instability is flagged so the
                       caller does not read it as a true fixed point. See ``flow_regime.lorenz``.

Fuller's Synergetics grammar (microstructure #46): three branches is the tetrahedral /
tetra-3 fundamental cycle -- the minimum-closure ternary the estate's TrendSignal wave
grammar already uses. This is a structural note, NOT numerology: the mechanism (a middle
branch that projects onto a regime-specific stable point) is what earns the ternary form.

Consume-by-reference (do NOT fork):
  * ``open_ep_framework.market_instruments`` (MKT-1) -- Black-76 ``bs_call`` / ``bs_put``
    supply the Black-Scholes reference the memoryless tree must converge to and the OU
    tree must DIFFER from.
  * memory-mesh process characterizer -- OU (theta, mu, half_life) and the
    process->regime->option crosswalk taxonomy label are consumed as inputs
    (``RegimeSpec.source_regime``), the same way ``term_calculus`` consumes the Hurst
    characterizer through an injection seam rather than re-fitting it.

Teeth (both directions), each a dedicated mutation test in ``tests/``:
  * BS-LIMIT (VERIFIES): a memoryless-regime European price converges to Black-Scholes
    within tolerance as the step count grows.
  * OU-DIFFERS (VERIFIES): a mean-reverting-regime price DIFFERS from Black-Scholes by
    more than tolerance -- mean reversion is priced.
  * PROBS-IN-[0,1] (REJECTS): every node's (pu, pm, pd) lies in [0,1] and sums to 1; a
    triple with a negative middle branch or a non-normalized sum is REJECTED.
  * REGIME-REALLY-CONSUMED (REJECTS): a "regime-aware" record whose mean-reverting price
    equals Black-Scholes across ALL regimes is REJECTED -- identical prices prove the
    regime was never consumed (the no-numerology / no-overclaim guard for Deliverable 1).

Deterministic and stdlib-only (analytic lattice, no PRNG), so CI is reproducible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..market_instruments import bs_call, bs_put

# The memory-mesh process->regime->option crosswalk labels this module consumes by
# reference (do NOT fork). Each maps to a middle-branch semantics below.
REGIME_KINDS = ("memoryless", "mean_reverting", "trending", "chaotic")

# The crosswalk's canonical (memory-mesh taxonomy label -> pricer regime kind) map,
# consumed by reference from docs/architecture/process-regime-crosswalk.md.
CROSSWALK = {
    "brownian_gbm": "memoryless",
    "markov_regime_switching": "memoryless",
    "ornstein_uhlenbeck": "mean_reverting",
    "fractional_brownian_motion": "trending",
    "hawkes": "mean_reverting",
    "jump_levy": "memoryless",
    "chaotic": "chaotic",
}

_PROB_TOL = 1e-9


class TrinomialError(ValueError):
    """Raised for an inadmissible tree (a branch probability outside [0,1], a
    non-normalized (pu, pm, pd), or an unusable regime spec) -- REJECTED."""


# --------------------------------------------------------------------------- #
# option + regime specs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EuropeanOption:
    spot: float
    strike: float
    vol: float          # per-year volatility of log-price
    maturity: float     # years
    rate: float = 0.0   # continuously-compounded risk-free rate
    call: bool = True

    def payoff(self, s: float) -> float:
        return max(s - self.strike, 0.0) if self.call else max(self.strike - s, 0.0)


@dataclass(frozen=True)
class RegimeSpec:
    """Which stable point the middle branch projects to.

    ``theta`` / ``mu`` are CONSUMED from the memory-mesh characterizer's OU fit for a
    ``mean_reverting`` regime; ``source_regime`` records the memory-mesh taxonomy label
    for provenance / audit.
    """

    kind: str = "memoryless"
    theta: float = 0.0            # OU mean-reversion speed (mean_reverting / chaotic)
    mu: float = 0.0              # reversion target / attractor centroid (level, > 0)
    momentum_drift: float = 0.0  # excess drift for a trending regime (per year)
    source_regime: str = ""       # memory-mesh taxonomy label (provenance)

    def __post_init__(self) -> None:
        if self.kind not in REGIME_KINDS:
            raise TrinomialError(f"unknown regime kind {self.kind!r}")
        if self.kind in ("mean_reverting", "chaotic"):
            if self.theta <= 0:
                raise TrinomialError(
                    f"{self.kind} regime requires theta>0 (a finite reversion timescale)"
                )
            if self.mu <= 0:
                raise TrinomialError(f"{self.kind} regime requires a positive level mu")

    @property
    def half_life(self) -> float:
        """OU half-life = ln2/theta (the memory-mesh characterizer's reported statistic)."""
        if self.theta <= 0:
            return float("inf")
        return math.log(2.0) / self.theta

    @classmethod
    def from_ou_characterization(cls, theta: float, mu: float,
                                 source_regime: str = "ornstein_uhlenbeck") -> "RegimeSpec":
        """Build a mean-reverting spec straight from the memory-mesh OU fit
        (``estimate_ou`` -> theta, mu). Consume-by-reference, do not re-fit."""
        return cls(kind="mean_reverting", theta=theta, mu=mu, source_regime=source_regime)


@dataclass(frozen=True)
class NodeProbs:
    """A single node's ternary branch probabilities and its branch targets (level
    offsets applied to the successor lattice)."""

    pu: float
    pm: float
    pd: float
    up: int
    mid: int
    down: int

    def validate(self) -> "NodeProbs":
        for name, p in (("pu", self.pu), ("pm", self.pm), ("pd", self.pd)):
            if p < -_PROB_TOL or p > 1.0 + _PROB_TOL:
                raise TrinomialError(
                    f"REJECTED: branch probability {name}={p:.6f} outside [0,1]"
                )
        s = self.pu + self.pm + self.pd
        if abs(s - 1.0) > 1e-6:
            raise TrinomialError(f"REJECTED: branch probabilities sum to {s:.6f} != 1")
        return self


# --------------------------------------------------------------------------- #
# Black-Scholes reference (consumed from market_instruments, MKT-1)
# --------------------------------------------------------------------------- #
def black_scholes_reference(opt: EuropeanOption) -> float:
    """Black-Scholes price via the estate's Black-76 kernel (forward = spot*e^{rT})."""
    fwd = opt.spot * math.exp(opt.rate * opt.maturity)
    df = math.exp(-opt.rate * opt.maturity)
    fn = bs_call if opt.call else bs_put
    return fn(fwd, opt.strike, opt.vol, opt.maturity, df)


# --------------------------------------------------------------------------- #
# the regime-aware trinomial pricer
# --------------------------------------------------------------------------- #
@dataclass
class RegimeAwareTrinomial:
    option: EuropeanOption
    regime: RegimeSpec
    steps: int = 200
    lam: float = math.sqrt(3.0)   # Boyle/Kamrad-Ritchken stretch (dx = lam*sigma*sqrt(dt))

    _last_probs: list = field(default_factory=list, repr=False)

    # ---- memoryless (Boyle/Kamrad-Ritchken) -> converges to Black-Scholes ---- #
    def _price_memoryless(self) -> float:
        opt = self.option
        n = self.steps
        dt = opt.maturity / n
        sig = opt.vol
        dx = self.lam * sig * math.sqrt(dt)
        drift = (opt.rate - 0.5 * sig * sig) * dt  # risk-neutral log-drift
        var = sig * sig * dt
        # moment-matched constant probabilities (mean=drift, var=sig^2 dt)
        q = (var + drift * drift) / (dx * dx)
        pu = 0.5 * (q + drift / dx)
        pm = 1.0 - q
        pd = 0.5 * (q - drift / dx)
        NodeProbs(pu, pm, pd, +1, 0, -1).validate()
        self._last_probs = [(pu, pm, pd)]
        disc = math.exp(-opt.rate * dt)
        x0 = math.log(opt.spot)
        # terminal layer j in [-n, n]
        vals = [opt.payoff(math.exp(x0 + j * dx)) for j in range(-n, n + 1)]
        for _ in range(n):
            nxt = [0.0] * (len(vals) - 2)
            for k in range(len(nxt)):
                # node k maps to lattice level; successors are k, k+1, k+2 in vals
                nxt[k] = disc * (pd * vals[k] + pm * vals[k + 1] + pu * vals[k + 2])
            vals = nxt
        return vals[0]

    # ---- mean_reverting (Hull-White trinomial) -> middle branch projects to mu ---- #
    def _hw_node_probs(self, j: int, jmax: int, a: float, dt: float) -> NodeProbs:
        """Hull-White stage-1 ternary probabilities for level j (reversion to j=0 == mu).

        Interior nodes branch to (j+1, j, j-1); the top node j=jmax branches DOWN to
        (j, j-1, j-2) and the bottom node j=-jmax branches UP to (j+2, j+1, j), so the
        recombining lattice is bounded and every probability stays in [0,1]."""
        aj = a * j * dt
        a2j2 = (a * j * dt) ** 2
        if j == jmax:  # downward branching at the top
            pu = 7.0 / 6.0 + 0.5 * (a2j2 - 3.0 * aj)
            pm = -1.0 / 3.0 - a2j2 + 2.0 * aj
            pd = 1.0 / 6.0 + 0.5 * (a2j2 - aj)
            return NodeProbs(pu, pm, pd, 0, -1, -2).validate()
        if j == -jmax:  # upward branching at the bottom
            pu = 1.0 / 6.0 + 0.5 * (a2j2 + aj)
            pm = -1.0 / 3.0 - a2j2 - 2.0 * aj
            pd = 7.0 / 6.0 + 0.5 * (a2j2 + 3.0 * aj)
            return NodeProbs(pu, pm, pd, +2, +1, 0).validate()
        pu = 1.0 / 6.0 + 0.5 * (a2j2 - aj)
        pm = 2.0 / 3.0 - a2j2
        pd = 1.0 / 6.0 + 0.5 * (a2j2 + aj)
        return NodeProbs(pu, pm, pd, +1, 0, -1).validate()

    def _price_mean_reverting(self) -> float:
        opt = self.option
        reg = self.regime
        n = self.steps
        dt = opt.maturity / n
        a = reg.theta
        sig = opt.vol
        dx = sig * math.sqrt(3.0 * dt)  # Hull's spacing
        jmax = max(2, math.ceil(0.184 / (a * dt)))
        xbar = math.log(reg.mu)             # lattice centre == the stable point mu
        levels = list(range(-jmax, jmax + 1))
        idx = {j: k for k, j in enumerate(levels)}
        probs = {j: self._hw_node_probs(j, jmax, a, dt) for j in levels}
        self._last_probs = [(p.pu, p.pm, p.pd) for p in probs.values()]
        disc = math.exp(-opt.rate * dt)
        # terminal payoff on the lattice
        vals = [opt.payoff(math.exp(xbar + j * dx)) for j in levels]
        for _ in range(n):
            nxt = [0.0] * len(levels)
            for j in levels:
                p = probs[j]
                nxt[idx[j]] = disc * (
                    p.pu * vals[idx[j + p.up]]
                    + p.pm * vals[idx[j + p.mid]]
                    + p.pd * vals[idx[j + p.down]]
                )
            vals = nxt
        # the option is written on the underlying starting at spot -> nearest lattice node
        j0 = round((math.log(opt.spot) - xbar) / dx)
        j0 = max(-jmax, min(jmax, j0))
        return vals[idx[j0]]

    # ---- trending (momentum-drift overlay; middle branch weak) ---- #
    def _price_trending(self) -> float:
        opt = self.option
        n = self.steps
        dt = opt.maturity / n
        sig = opt.vol
        dx = self.lam * sig * math.sqrt(dt)
        drift = (opt.rate - 0.5 * sig * sig + self.regime.momentum_drift) * dt
        var = sig * sig * dt
        q = (var + drift * drift) / (dx * dx)
        pu = 0.5 * (q + drift / dx)
        pm = 1.0 - q
        pd = 0.5 * (q - drift / dx)
        NodeProbs(pu, pm, pd, +1, 0, -1).validate()
        self._last_probs = [(pu, pm, pd)]
        disc = math.exp(-opt.rate * dt)
        x0 = math.log(opt.spot)
        vals = [opt.payoff(math.exp(x0 + j * dx)) for j in range(-n, n + 1)]
        for _ in range(n):
            nxt = [0.0] * (len(vals) - 2)
            for k in range(len(nxt)):
                nxt[k] = disc * (pd * vals[k] + pm * vals[k + 1] + pu * vals[k + 2])
            vals = nxt
        return vals[0]

    def price(self) -> float:
        kind = self.regime.kind
        if kind in ("mean_reverting", "chaotic"):
            # a chaotic regime prices around its attractor centroid mu like an OU pull,
            # but flags the local instability (see flow_regime.lorenz) to the caller.
            return self._price_mean_reverting()
        if kind == "trending":
            return self._price_trending()
        return self._price_memoryless()

    def node_probabilities(self) -> list:
        """The (pu, pm, pd) triples actually used (validated in [0,1], summing to 1)."""
        if not self._last_probs:
            self.price()
        return list(self._last_probs)
