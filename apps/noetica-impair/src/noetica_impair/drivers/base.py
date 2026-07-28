"""Driver ABC + RunContext (invariant 0.2).

``MechanicalDriver`` and ``TopicalDriver`` both implement
``prepare(prompt, dose) -> RunContext``. The battery only ever sees the resulting
``Subject``, so the same measurement applies to a weight-level lesion and to a
charged-topic prompt. That symmetry is what makes section 7's equivalence mapping
("charged-topic X reads as ALCOHOL@0.4") a measurement rather than an analogy.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

import torch

from ..probes.base import Subject


@dataclass
class RunContext:
    subject: Subject
    driver: str
    dose: float
    detail: dict[str, Any] = field(default_factory=dict)


class Driver(abc.ABC):
    name: str = "driver"

    @abc.abstractmethod
    def prepare(self, prompt: str, dose: float) -> RunContext: ...

    @abc.abstractmethod
    def subject(self, dose: float) -> Subject:
        """The Subject the battery measures at this dose."""


class ModelSubject:
    """Adapts a HF causal LM to the ``Subject`` protocol.

    ``loglikelihood`` sums token logprobs of the continuation conditioned on the
    prompt -- computed in one forward pass, no sampling, so it is deterministic and
    unaffected by generation settings. Probes lean on this rather than free
    generation wherever possible (see probes.base.choose).
    """

    def __init__(self, model, tokenizer, device, *, prefix: str = "") -> None:
        self.model = model
        self.tok = tokenizer
        self.device = device
        self.prefix = prefix

    def _ids(self, text: str) -> torch.Tensor:
        return self.tok(text, return_tensors="pt", add_special_tokens=False).input_ids.to(
            self.device
        )

    @torch.no_grad()
    def loglikelihood(self, prompt: str, continuation: str) -> float:
        full = self.prefix + prompt
        p_ids = self._ids(full)
        c_ids = self._ids(continuation)
        ids = torch.cat([p_ids, c_ids], dim=1)
        logits = self.model(ids).logits.float()
        # Predict token t from position t-1.
        logprobs = torch.log_softmax(logits[:, :-1], dim=-1)
        target = ids[:, 1:]
        gathered = logprobs.gather(-1, target.unsqueeze(-1)).squeeze(-1)
        n_cont = c_ids.shape[1]
        return float(gathered[:, -n_cont:].sum().item())

    @torch.no_grad()
    def generate(self, prompt: str, *, max_new_tokens: int = 64) -> str:
        ids = self._ids(self.prefix + prompt)
        out = self.model.generate(
            ids, max_new_tokens=max_new_tokens, do_sample=False,
            pad_token_id=getattr(self.tok, "pad_token_id", None)
            or getattr(self.tok, "eos_token_id", None),
        )
        return self.tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)
