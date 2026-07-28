"""Invariant 0.3 / milestone M0: at dose=0 an installed intervention is a no-op.

Bit-for-bit, not approximately. If dose=0 drifts, every delta in the study is
measured against a moving baseline and nothing downstream means anything.
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


def dense_interventions():
    return [
        ("distance_decay", DistanceDecayAttenuation(alpha=0.5, window=4, seed=1)),
        ("broaden", AttentionBroadening(tau=3.0, seed=1)),
        ("residual", DepthScaledResidualNoise(sigma=0.5, seed=1)),
        ("logits_flat", LogitOps(k_flat=2.0, eos_bias=5.0, magnitude_gain=0.5, seed=1)),
        ("logits_sharp", LogitOps(k_sharp=2.0, eos_bias=-5.0, seed=1)),
    ]


@pytest.mark.parametrize("name,iv", dense_interventions(), ids=lambda x: x if isinstance(x, str) else "")
def test_dense_intervention_inert_at_zero(toy_dense, ids, name, iv):
    ref = prepared_reference(toy_dense, ids)
    rig = Rig(toy_dense.model, toy_dense.meta).add(iv)
    with rig:
        rig.set_dose(0.0)
        got = logits_of(toy_dense, ids)
        assert torch.equal(ref, got), (
            f"{name}: dose=0 perturbed output by {(ref - got).abs().max().item():.3e}"
        )


def test_full_stack_inert_at_zero(toy_dense, ids):
    """All dense interventions installed together are still jointly inert."""
    ref = prepared_reference(toy_dense, ids)
    rig = Rig(toy_dense.model, toy_dense.meta)
    for _, iv in dense_interventions():
        rig.add(iv)
    with rig:
        rig.set_dose(0.0)
        assert torch.equal(ref, logits_of(toy_dense, ids))


def test_router_ops_inert_at_zero(toy_moe, ids):
    ref = logits_of(toy_moe, ids)
    rig = Rig(toy_moe.model, toy_moe.meta).add(
        RouterOps(sigma_r=1.0, k_r=2.0, anti_route=1.0, expert_dropout=0.5,
                  topk_reduce_at=0.7, seed=1)
    )
    with rig:
        rig.set_dose(0.0)
        got = logits_of(toy_moe, ids)
        assert torch.equal(ref, got), (
            f"router: dose=0 perturbed output by {(ref - got).abs().max().item():.3e}"
        )


def test_removal_restores_baseline(toy_dense, ids):
    """After remove(), a nonzero dose leaves no residue."""
    ref = prepared_reference(toy_dense, ids)
    rig = Rig(toy_dense.model, toy_dense.meta).add(DepthScaledResidualNoise(sigma=1.0, seed=1))
    rig.install()
    rig.set_dose(0.9)
    _ = logits_of(toy_dense, ids)
    rig.remove()
    assert torch.equal(ref, logits_of(toy_dense, ids))


def test_zero_magnitude_is_inert_even_at_full_dose(toy_dense, ids):
    """A preset that sets a knob to zero must not perturb, whatever the dose."""
    ref = prepared_reference(toy_dense, ids)
    rig = Rig(toy_dense.model, toy_dense.meta).add(DepthScaledResidualNoise(sigma=0.0, seed=1))
    with rig:
        rig.set_dose(1.0)
        assert torch.equal(ref, logits_of(toy_dense, ids))


def test_dose_bounds_enforced():
    iv = DepthScaledResidualNoise(sigma=1.0)
    for bad in (-0.1, 1.1, 2.0):
        with pytest.raises(ValueError):
            iv.set_dose(bad)
