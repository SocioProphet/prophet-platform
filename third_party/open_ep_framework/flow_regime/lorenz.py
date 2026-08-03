"""Low-dimensional flow-regime lens: Lorenz / turbulence <-> Navier-Stokes (FRL-1).

The Lorenz (1963) system is the canonical THREE-variable reduction of Rayleigh-Benard
convection -- a Navier-Stokes (incompressible, buoyancy-driven) flow truncated to its
first Fourier modes:

    dx/dt = sigma (y - x)
    dy/dt = x (rho - z) - y
    dz/dt = x y - beta z

``x`` ~ convective overturning rate, ``y`` / ``z`` ~ horizontal / vertical temperature
structure; ``rho`` is the reduced Rayleigh number (drive), ``sigma`` the Prandtl number,
``beta`` the geometry. This module reads the flow REGIME the way the memory-mesh
characterizer reads a market series' memory regime, and MAPS the two:

  * fixed-point stability from the Jacobian eigenvalues, and
  * the largest Lyapunov exponent (positive => sensitive dependence => chaos),

classify **laminar** (a stable fixed point; all eigenvalue real parts negative;
Lyapunov <= 0) vs **turbulent** (a strange attractor; a positive Lyapunov exponent).

Consume-by-reference (do NOT fork):
  * memory-mesh regime characterizer -- the Lyapunov ESTIMATOR and the regime TAXONOMY
    are the memory-mesh property. We expose an INJECTION SEAM ``lyapunov_fn`` (exactly
    the pattern ``term_calculus`` uses for the Hurst characterizer): when a series-based
    estimator (memory-mesh ``lyapunov_rosenstein``) is injected it is used; otherwise a
    local, deterministic Benettin exponent (variational, using the analytic Jacobian --
    the correct method for a KNOWN vector field, not a re-fit of the series estimator) is
    the hermetic-CI fallback. The taxonomy map is fixed by reference:
        chaotic            <-> turbulent
        memoryless/stable  <-> laminar
    and the sign-agreement tooth asserts the two never disagree.

Market vol-cascade <-> turbulent energy cascade (documented, ANALOGUE only):
  Kolmogorov's turbulent energy cascade (energy injected at large scales, dissipated at
  small scales, with intermittency / multifractal scaling) is the physical twin of the
  market VOLATILITY cascade. Ghashghaie et al. (Nature, 1996) showed FX returns share
  the multifractal, cascade-like statistics of hydrodynamic turbulence; rough-volatility
  (Gatheral-Jaisson-Rosenbaum) finds volatility is itself a fractional process with
  H~=0.1 -- the ANTI-PERSISTENT / intermittent end of the memory-mesh Hurst axis. The
  vol cascade maps to the turbulent cascade through that Hurst / multifractal axis. This
  is a characterization LENS, not an identity.

NO-OVERCLAIM GUARD (Deliverable 2 honesty tooth): this module is an ANALOGUE /
characterization lens. It does NOT solve, prove, or bear on the Navier-Stokes existence
and smoothness (Clay Millennium) problem. Any record claiming to do so is REJECTED
(``reject_navier_stokes_overclaim``); the schema pins ``scope`` to
``analogue_characterization_only``.

Deterministic and stdlib-only (fixed-seed-free RK4 + analytic Jacobian).
"""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass

# The classic chaotic Lorenz parameter set (sigma, rho, beta).
LORENZ_CLASSIC = (10.0, 28.0, 8.0 / 3.0)

# Chaos threshold on the largest Lyapunov exponent. Consumed BY REFERENCE from the
# memory-mesh characterizer (memory_regime_estimators.CHAOS_LAMBDA == 0.30): a lambda
# above this is chaotic/turbulent. Kept identical so the two lenses agree by construction.
CHAOS_LAMBDA = 0.30

# The fixed memory-mesh-taxonomy <-> flow-regime map (consume-by-reference).
TAXONOMY_TO_FLOW = {
    "chaotic": "turbulent",
    "memoryless": "laminar",
    "short_decaying": "laminar",
    "long_memory": "laminar",  # persistent but not (necessarily) sensitive-dependent
}

# Phrases that make a record an illegitimate Navier-Stokes existence/smoothness claim.
_NS_ACTS = ("solve", "solved", "solves", "prove", "proved", "proves", "proof",
            "resolve", "resolves", "settle", "settles", "establish", "establishes")
_NS_SUBJECTS = ("navier-stokes", "navier stokes", "navierstokes")
_NS_TARGETS = ("existence", "smoothness", "regularity", "millennium", "global solution",
               "blow-up", "blowup", "well-posed", "well posed")


class FlowRegimeError(ValueError):
    """Raised for an inadmissible flow record (bad params, an overclaim) -- REJECTED."""


LorenzParams = tuple  # (sigma, rho, beta)


# --------------------------------------------------------------------------- #
# vector field, fixed points, Jacobian
# --------------------------------------------------------------------------- #
def lorenz_deriv(state, params: LorenzParams):
    x, y, z = state
    sigma, rho, beta = params
    return (sigma * (y - x), x * (rho - z) - y, x * y - beta * z)


def fixed_points(params: LorenzParams) -> list:
    """Fixed points of the Lorenz flow.

    The origin always; for rho>1 the convective pair C+/- =
    (+-sqrt(beta(rho-1)), +-sqrt(beta(rho-1)), rho-1)."""
    sigma, rho, beta = params
    pts = [("origin", (0.0, 0.0, 0.0))]
    if rho > 1.0:
        r = math.sqrt(beta * (rho - 1.0))
        pts.append(("C+", (r, r, rho - 1.0)))
        pts.append(("C-", (-r, -r, rho - 1.0)))
    return pts


def jacobian(state, params: LorenzParams):
    x, y, z = state
    sigma, rho, beta = params
    return [
        [-sigma, sigma, 0.0],
        [rho - z, -1.0, -x],
        [y, x, -beta],
    ]


def _cubic_roots(a: float, b: float, c: float, d: float):
    """All three (complex) roots of a x^3 + b x^2 + c x + d = 0 (a != 0)."""
    b, c, d = b / a, c / a, d / a
    # depressed cubic t^3 + p t + q with x = t - b/3
    p = c - b * b / 3.0
    q = 2.0 * b ** 3 / 27.0 - b * c / 3.0 + d
    shift = -b / 3.0
    disc = (q / 2.0) ** 2 + (p / 3.0) ** 3
    roots = []
    if abs(p) < 1e-14 and abs(q) < 1e-14:
        return [complex(shift)] * 3
    sqrt_disc = cmath.sqrt(disc)
    u = (-q / 2.0 + sqrt_disc)
    u = u ** (1.0 / 3.0) if u == 0 else cmath.exp(cmath.log(u) / 3.0)
    for k in range(3):
        w = cmath.exp(2j * cmath.pi * k / 3.0) * u
        if abs(w) < 1e-14:
            continue
        v = -p / (3.0 * w)
        roots.append(w + v + shift)
    # pad if degenerate
    while len(roots) < 3:
        roots.append(complex(shift))
    return roots[:3]


def eigenvalues(state, params: LorenzParams):
    """Eigenvalues of the Jacobian at ``state`` (via the characteristic cubic
    lambda^3 - tr lambda^2 + (sum principal 2x2 minors) lambda - det = 0)."""
    J = jacobian(state, params)
    tr = J[0][0] + J[1][1] + J[2][2]
    m11 = J[1][1] * J[2][2] - J[1][2] * J[2][1]
    m22 = J[0][0] * J[2][2] - J[0][2] * J[2][0]
    m33 = J[0][0] * J[1][1] - J[0][1] * J[1][0]
    minors = m11 + m22 + m33
    det = (
        J[0][0] * (J[1][1] * J[2][2] - J[1][2] * J[2][1])
        - J[0][1] * (J[1][0] * J[2][2] - J[1][2] * J[2][0])
        + J[0][2] * (J[1][0] * J[2][1] - J[1][1] * J[2][0])
    )
    return _cubic_roots(1.0, -tr, minors, -det)


def is_stable_fixed_point(state, params: LorenzParams) -> bool:
    """A fixed point is (linearly) stable iff every eigenvalue has negative real part."""
    return all(ev.real < -1e-9 for ev in eigenvalues(state, params))


def any_stable_fixed_point(params: LorenzParams) -> bool:
    return any(is_stable_fixed_point(s, params) for _, s in fixed_points(params))


# --------------------------------------------------------------------------- #
# RK4 integrator + Benettin largest Lyapunov exponent (local fallback estimator)
# --------------------------------------------------------------------------- #
def _rk4_step(state, params, dt):
    def add(s, k, h):
        return (s[0] + h * k[0], s[1] + h * k[1], s[2] + h * k[2])
    k1 = lorenz_deriv(state, params)
    k2 = lorenz_deriv(add(state, k1, dt / 2), params)
    k3 = lorenz_deriv(add(state, k2, dt / 2), params)
    k4 = lorenz_deriv(add(state, k3, dt), params)
    return (
        state[0] + dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
        state[1] + dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
        state[2] + dt / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]),
    )


def trajectory(params: LorenzParams, state0=(1.0, 1.0, 1.0), dt: float = 0.01,
               n: int = 4000, transient: int = 1000):
    """Deterministic RK4 trajectory (after discarding a transient) as a list of states."""
    s = state0
    for _ in range(transient):
        s = _rk4_step(s, params, dt)
    out = []
    for _ in range(n):
        s = _rk4_step(s, params, dt)
        out.append(s)
    return out


def benettin_lyapunov(params: LorenzParams, state0=(1.0, 1.0, 1.0), dt: float = 0.01,
                      n: int = 6000, transient: int = 2000, d0: float = 1e-8) -> float:
    """Largest Lyapunov exponent by the Benettin (1980) variational method.

    Two nearby trajectories are advanced by the SAME RK4 flow; their separation is
    renormalized to ``d0`` each step and the mean log-growth is accumulated. This uses
    the analytic flow of a KNOWN vector field -- it is NOT a re-fit of the memory-mesh
    series estimator, which is consumed through the ``lyapunov_fn`` seam instead.
    """
    s = state0
    for _ in range(transient):
        s = _rk4_step(s, params, dt)
    # perturbed companion
    sp = (s[0] + d0, s[1], s[2])
    total = 0.0
    for _ in range(n):
        s = _rk4_step(s, params, dt)
        sp = _rk4_step(sp, params, dt)
        dx = (sp[0] - s[0], sp[1] - s[1], sp[2] - s[2])
        dist = math.sqrt(dx[0] ** 2 + dx[1] ** 2 + dx[2] ** 2)
        if dist <= 0:
            continue
        total += math.log(dist / d0)
        scale = d0 / dist
        sp = (s[0] + dx[0] * scale, s[1] + dx[1] * scale, s[2] + dx[2] * scale)
    return total / (n * dt)


# --------------------------------------------------------------------------- #
# classifier
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FlowClassification:
    params: LorenzParams
    lambda_max: float
    regime: str                 # "laminar" | "turbulent"
    stable_fixed_point: bool
    fixed_point_report: tuple    # ((label, max_real_eigenvalue, stable), ...)
    lyapunov_source: str        # "benettin" | injected estimator name

    @property
    def is_turbulent(self) -> bool:
        return self.regime == "turbulent"


def classify_flow(params: LorenzParams, lyapunov_fn=None,
                  state0=(1.0, 1.0, 1.0)) -> FlowClassification:
    """Classify a Lorenz parameter set as laminar or turbulent.

    ``lyapunov_fn`` is the consume-by-reference injection seam: if given, it is called
    as ``lyapunov_fn(series)`` on a trajectory coordinate (the memory-mesh
    ``lyapunov_rosenstein`` fits this signature); otherwise the local Benettin exponent
    is used. Turbulent iff lambda_max > CHAOS_LAMBDA (the memory-mesh threshold)."""
    sigma, rho, beta = params
    if sigma <= 0 or beta <= 0 or rho < 0:
        raise FlowRegimeError(f"REJECTED: non-physical Lorenz params {params}")
    if lyapunov_fn is not None:
        series = [s[0] for s in trajectory(params, state0=state0)]
        lam = float(lyapunov_fn(series))
        source = getattr(lyapunov_fn, "__name__", "injected")
    else:
        lam = benettin_lyapunov(params, state0=state0)
        source = "benettin"
    report = tuple(
        (label, max(ev.real for ev in eigenvalues(s, params)),
         is_stable_fixed_point(s, params))
        for label, s in fixed_points(params)
    )
    stable = any(rep[2] for rep in report)
    regime = "turbulent" if lam > CHAOS_LAMBDA else "laminar"
    return FlowClassification(params, round(lam, 4), regime, stable, report, source)


# --------------------------------------------------------------------------- #
# taxonomy agreement + no-overclaim guard (the teeth)
# --------------------------------------------------------------------------- #
def flow_regime_for_taxonomy(memory_regime: str) -> str:
    """Map a memory-mesh taxonomy label to the expected flow regime (by reference)."""
    if memory_regime not in TAXONOMY_TO_FLOW:
        raise FlowRegimeError(f"unknown memory-mesh regime label {memory_regime!r}")
    return TAXONOMY_TO_FLOW[memory_regime]


def lyapunov_sign_agrees(classification: FlowClassification, memory_regime: str) -> bool:
    """The Lyapunov-sign flow regime must match the characterizer's taxonomy regime.

    chaotic (lambda>0) <-> turbulent; a stable/non-chaotic taxonomy label <-> laminar."""
    return classification.regime == flow_regime_for_taxonomy(memory_regime)


def reject_navier_stokes_overclaim(text) -> None:
    """REJECT any claim to solve/prove Navier-Stokes existence/smoothness.

    The lens is an analogue only; a record asserting it settles the Clay Millennium
    problem (or global existence / smoothness / regularity / blow-up) is inadmissible.
    """
    if text is None:
        return
    if isinstance(text, (list, tuple)):
        for t in text:
            reject_navier_stokes_overclaim(t)
        return
    low = str(text).lower()
    if not any(subj in low for subj in _NS_SUBJECTS):
        return
    has_act = any(act in low for act in _NS_ACTS)
    has_target = any(t in low for t in _NS_TARGETS)
    if has_act and has_target:
        raise FlowRegimeError(
            "REJECTED: Navier-Stokes existence/smoothness over-claim -- this lens is an "
            "ANALOGUE/characterization only and does not solve or prove the Clay problem"
        )
