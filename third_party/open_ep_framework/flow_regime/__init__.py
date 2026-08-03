"""Flow-regime module: the ternary-option <-> low-dimensional-turbulence synthesis.

Two contracts-with-teeth, one thesis -- a market process and a fluid flow are read by
the SAME regime lens (the memory-mesh characterizer's taxonomy), and each regime picks
a different pricing / stability mechanism:

  * ``trinomial`` (FRT-1) -- a regime-aware Boyle trinomial option pricer whose MIDDLE
    ("stay") branch projects to the regime's stable point (memoryless -> Black-Scholes;
    mean-reverting -> the OU reversion target ``mu``; trending -> drift-dominated;
    chaotic -> attractor centroid). Consumes ``market_instruments`` (Black-76) and the
    memory-mesh OU fit / crosswalk by reference.
  * ``lorenz`` (FRL-1) -- a Lorenz-style 3-variable Navier-Stokes reduction; Jacobian
    fixed-point stability + the largest Lyapunov exponent classify laminar vs turbulent,
    and the market vol-cascade is mapped to the turbulent energy cascade (Kolmogorov /
    multifractal; Ghashghaie 1996; rough-vol H~=0.1). Analogue only -- an explicit
    no-overclaim guard rejects any claim to solve/prove Navier-Stokes existence/smoothness.

Metaphor -> mechanism, NOT numerology: the ternary form and the turbulence lens are
earned by the mechanism (a middle branch that lands on a regime-specific stable point;
a Lyapunov sign that must agree with the characterizer), and every claim carries a
falsifying tooth.

Deterministic and stdlib-only.
"""
from . import lorenz, trinomial  # noqa: F401

__all__ = ["trinomial", "lorenz"]
