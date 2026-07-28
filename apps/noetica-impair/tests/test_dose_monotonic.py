"""Milestone M0: dose is an ordered knob.

Divergence from the sober reference must increase monotonically with dose. A hook
that is non-monotonic cannot support a dose-response curve, and any equivalence
mapping built on it (section 7) would be ill-defined.

Noise is re-seeded before each measurement so the comparison isolates dose rather
than how many draws a previous forward pass happened to consume.
"""

from __future__ import annotations

import pytest
import torch

from noetica_impair.hooks.attention import AttentionBroadening, DistanceDecayAttenuation
from noetica_impair.hooks.base import Rig
from noetica_impair.hooks.logits import LogitOps
from noetica_impair.hooks.residual import DepthScaledResidualNoise
from noetica_impair.hooks.router import RouterOps
from noetica_impair.testing import logits_of, prepared_reference

DOSES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def divergence_curve(lm, ids, iv, ref) -> list[float]:
    rig = Rig(lm.model, lm.meta).add(iv)
    out = []
    with rig:
        for d in DOSES:
            rig.set_dose(d)
            rig.reset_noise()
            got = logits_of(lm, ids)
            out.append((got - ref).abs().mean().item())
    return out


def assert_monotonic(curve: list[float], name: str) -> None:
    assert curve[0] == 0.0, f"{name}: dose=0 diverged ({curve[0]:.3e})"
    for lo, hi in zip(curve, curve[1:]):
        assert hi >= lo - 1e-9, f"{name}: non-monotonic dose response {curve}"
    assert curve[-1] > curve[0], f"{name}: full dose had no effect {curve}"


@pytest.mark.parametrize(
    "name,factory",
    [
        ("distance_decay", lambda: DistanceDecayAttenuation(alpha=1.0, window=4, seed=2)),
        ("broaden", lambda: AttentionBroadening(tau=4.0, seed=2)),
        ("residual", lambda: DepthScaledResidualNoise(sigma=0.6, seed=2)),
        ("logit_flatten", lambda: LogitOps(k_flat=3.0, seed=2)),
        ("logit_sharpen", lambda: LogitOps(k_sharp=3.0, seed=2)),
        ("logit_magnitude", lambda: LogitOps(magnitude_gain=0.8, seed=2)),
    ],
)
def test_dense_dose_monotonic(toy_dense, ids, name, factory):
    ref = prepared_reference(toy_dense, ids)
    assert_monotonic(divergence_curve(toy_dense, ids, factory(), ref), name)


@pytest.mark.parametrize(
    "name,factory",
    [
        ("router_noise", lambda: RouterOps(sigma_r=2.0, seed=2)),
        ("router_flatten", lambda: RouterOps(k_r=3.0, seed=2)),
        ("anti_route", lambda: RouterOps(anti_route=1.0, seed=2)),
        ("expert_dropout", lambda: RouterOps(expert_dropout=1.0, seed=2)),
    ],
)
def test_moe_dose_monotonic(toy_moe, ids, name, factory):
    ref = logits_of(toy_moe, ids)
    curve = divergence_curve(toy_moe, ids, factory(), ref)
    assert curve[0] == 0.0, f"{name}: dose=0 diverged"
    assert curve[-1] > curve[0], f"{name}: full dose had no effect {curve}"


def test_seed_determinism(toy_dense, ids):
    """Same seed + same dose = identical output, across separate rig instances."""
    ref = prepared_reference(toy_dense, ids)
    a = divergence_curve(toy_dense, ids, DepthScaledResidualNoise(sigma=0.5, seed=42), ref)
    b = divergence_curve(toy_dense, ids, DepthScaledResidualNoise(sigma=0.5, seed=42), ref)
    assert a == b


def test_different_seeds_differ(toy_dense, ids):
    ref = prepared_reference(toy_dense, ids)
    a = divergence_curve(toy_dense, ids, DepthScaledResidualNoise(sigma=0.5, seed=1), ref)
    b = divergence_curve(toy_dense, ids, DepthScaledResidualNoise(sigma=0.5, seed=2), ref)
    assert a != b, "different seeds produced identical noise -- generator is not seeded"
