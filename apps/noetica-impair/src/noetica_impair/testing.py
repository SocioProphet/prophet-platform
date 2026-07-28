"""Test helpers, in-package so tests import them absolutely (no relative imports)."""

from __future__ import annotations

import torch

from .hooks.attention import attach_editor


def logits_of(lm, ids) -> torch.Tensor:
    with torch.no_grad():
        return lm.model(ids).logits.detach().clone()


def prepared_reference(lm, ids) -> torch.Tensor:
    """Forward pass with the impaired attention impl active but zero edits registered.

    The correct baseline for the inert-at-zero invariant: it isolates "dose=0 perturbs
    nothing" from "swapping the attention kernel perturbs nothing", which is a separate
    claim tested in test_attention_impl_faithful.
    """
    attach_editor(lm.model)
    return logits_of(lm, ids)
