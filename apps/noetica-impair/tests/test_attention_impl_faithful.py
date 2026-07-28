"""The attention-kernel swap must not itself be a lesion.

Guards the trap that motivated this file: a custom attention function registered
without a matching mask function receives ``attention_mask=None`` and attends
BIDIRECTIONALLY, silently making every sober baseline non-causal. That failure shows
up here as a large divergence (~2.5e-01 on this fixture) instead of float noise.
"""

from __future__ import annotations

import torch

from noetica_impair.hooks import attention as A
from noetica_impair.models import loaders
from noetica_impair.testing import logits_of


def test_impaired_impl_matches_sdpa():
    lm = loaders.load("toy-dense", seed=99, device="cpu")
    g = torch.Generator().manual_seed(3)
    ids = torch.randint(0, 256, (2, 32), generator=g)

    lm.model.set_attn_implementation("sdpa")
    ref = logits_of(lm, ids)

    A.attach_editor(lm.model)
    assert lm.model.config._attn_implementation == A.ATTN_IMPL_NAME
    got = logits_of(lm, ids)

    assert torch.allclose(ref, got, atol=1e-5, rtol=1e-4), (
        f"impaired attention diverges from sdpa by {(ref - got).abs().max().item():.3e}"
    )


def test_causal_mask_is_registered():
    """Directly assert the mask function exists under our impl name."""
    from transformers.masking_utils import ALL_MASK_ATTENTION_FUNCTIONS

    A.ensure_registered()
    assert A.ATTN_IMPL_NAME in ALL_MASK_ATTENTION_FUNCTIONS


def test_attention_is_still_causal():
    """A future token must not change an earlier position's logits."""
    lm = loaders.load("toy-dense", seed=5, device="cpu")
    A.attach_editor(lm.model)
    g = torch.Generator().manual_seed(11)
    ids = torch.randint(0, 256, (1, 16), generator=g)
    a = logits_of(lm, ids)

    ids2 = ids.clone()
    ids2[0, -1] = (ids2[0, -1] + 1) % 256  # perturb only the last token
    b = logits_of(lm, ids2)

    assert torch.allclose(a[0, :-1], b[0, :-1], atol=1e-6), (
        "changing the final token altered earlier positions -> attention is not causal"
    )
