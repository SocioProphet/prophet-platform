"""Routing KL and the recorder that feeds it.

The metric existed with nothing producing its inputs, so it had never run. These tests
cover both halves and the depth profile that milestone M4 turns on.
"""

from __future__ import annotations

import math

import pytest
import torch

from noetica_impair.hooks.base import Rig
from noetica_impair.hooks.router import RouterOps
from noetica_impair.models import loaders
from noetica_impair.readout.routing_kl import (
    GateRecorder, compare_runs, depth_weighted_ratio, kl_rows, per_layer_kl, summarise,
)


def dist(*rows):
    t = torch.tensor(rows, dtype=torch.float32)
    return t / t.sum(-1, keepdim=True)


def test_kl_of_identical_distributions_is_zero():
    p = dist([0.7, 0.2, 0.1])
    assert float(kl_rows(p, p).item()) == pytest.approx(0.0, abs=1e-6)


def test_kl_is_positive_and_asymmetric():
    p, q = dist([0.9, 0.05, 0.05]), dist([0.34, 0.33, 0.33])
    fwd = float(kl_rows(p, q).item())
    rev = float(kl_rows(q, p).item())
    assert fwd > 0 and rev > 0
    assert fwd != pytest.approx(rev), "KL is not symmetric; the argument order matters"


def test_kl_handles_zeros_without_blowing_up():
    p, q = dist([1.0, 0.0, 0.0]), dist([0.0, 0.5, 0.5])
    v = float(kl_rows(p, q).item())
    assert math.isfinite(v) and v > 0


def test_per_layer_kl_only_compares_layers_present_in_both():
    sober = {0: [dist([0.5, 0.5])], 1: [dist([0.9, 0.1])]}
    impaired = {1: [dist([0.1, 0.9])], 2: [dist([0.5, 0.5])]}
    prof = per_layer_kl(sober, impaired)
    assert set(prof) == {1}, "a layer recorded on only one side cannot be compared"


def test_deep_shallow_ratio_detects_the_pfc_first_signature():
    """Divergence concentrated in later layers is the M4 result."""
    pfc_first = {0: 0.01, 1: 0.02, 2: 0.30, 3: 0.40}
    assert depth_weighted_ratio(pfc_first, n_layers=4) > 1.0
    assert summarise(pfc_first, 4)["pfc_first"] is True

    surface_first = {0: 0.40, 1: 0.30, 2: 0.02, 3: 0.01}
    assert depth_weighted_ratio(surface_first, n_layers=4) < 1.0
    assert summarise(surface_first, 4)["pfc_first"] is False


def test_ratio_is_nan_when_one_half_is_missing():
    assert math.isnan(depth_weighted_ratio({0: 0.1, 1: 0.2}, n_layers=8))


def test_compare_runs_warns_when_too_few_layers_to_call_it_a_profile():
    sober = {0: [dist([0.5, 0.5])], 1: [dist([0.5, 0.5])]}
    impaired = {0: [dist([0.9, 0.1])], 1: [dist([0.9, 0.1])]}
    out = compare_runs(sober, impaired, n_layers=2)
    assert "warning" in out and "not a depth profile" in out["warning"]


def test_compare_runs_warns_when_nothing_overlaps():
    out = compare_runs({0: [dist([0.5, 0.5])]}, {5: [dist([0.5, 0.5])]})
    assert "nothing to compare" in out["warning"]


# ── the recorder ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def moe():
    return loaders.load("toy-moe", seed=4, device="cpu")


@pytest.fixture(scope="module")
def ids():
    g = torch.Generator().manual_seed(9)
    return torch.randint(0, 256, (1, 24), generator=g)


def test_recorder_captures_a_distribution_per_layer(moe, ids):
    rec = GateRecorder().install(moe.model, moe.meta)
    try:
        moe.model(ids.to(moe.device))
    finally:
        rec.remove()
    assert rec.layers, "nothing recorded — the router hook never fired"
    for layer, chunks in rec.layers.items():
        t = torch.cat(chunks, 0)
        assert t.dim() == 2
        assert torch.allclose(t.sum(-1), torch.ones(t.shape[0]), atol=1e-4), \
            "recorded rows must be probability distributions, not raw logits"


def test_recorder_refuses_a_dense_model():
    """This metric is MoE-only; a dense run has no expert distribution."""
    dense = loaders.load("toy-dense", seed=4, device="cpu")
    with pytest.raises(RuntimeError, match="MoE-only|router_path"):
        GateRecorder().install(dense.model, dense.meta)


def test_sober_vs_sober_is_zero_divergence(moe, ids):
    """The paired-control sanity check: same rig, no intervention, no divergence."""
    a, b = GateRecorder(), GateRecorder()
    for rec in (a, b):
        rec.install(moe.model, moe.meta)
        moe.model(ids.to(moe.device))
        rec.remove()
    prof = per_layer_kl(a.snapshot(), b.snapshot())
    assert prof, "no layers compared"
    assert max(prof.values()) == pytest.approx(0.0, abs=1e-6)


def test_router_noise_produces_measurable_divergence(moe, ids):
    """An actual intervention must move the metric it is measured by."""
    sober = GateRecorder().install(moe.model, moe.meta)
    moe.model(ids.to(moe.device))
    sober.remove()

    rig = Rig(moe.model, moe.meta).add(RouterOps(sigma_r=2.5, seed=1))
    impaired = GateRecorder()
    with rig:
        rig.set_dose(0.8)
        impaired.install(moe.model, moe.meta)
        moe.model(ids.to(moe.device))
        impaired.remove()

    prof = per_layer_kl(sober.snapshot(), impaired.snapshot())
    assert prof and max(prof.values()) > 0, "router noise produced no routing divergence"


def test_recorder_respects_its_token_cap(moe, ids):
    rec = GateRecorder(max_tokens_per_layer=8).install(moe.model, moe.meta)
    try:
        for _ in range(4):
            moe.model(ids.to(moe.device))
    finally:
        rec.remove()
    for chunks in rec.layers.values():
        assert sum(t.shape[0] for t in chunks) <= 8
