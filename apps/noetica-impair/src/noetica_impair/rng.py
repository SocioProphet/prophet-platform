"""Seeded noise source.

Invariant 0.5: every stochastic intervention draws from a generator whose seed is
recorded in provenance. Two runs with the same seed and the same dose must produce
the same noise, on any device.

Device generators are not available everywhere (notably MPS), so noise is drawn on
CPU and moved. That costs a copy but makes the draw sequence identical regardless of
which plane the run lands on, which is what makes local and cloud runs comparable.
"""

from __future__ import annotations

import torch


class SeededNoise:
    def __init__(self, seed: int) -> None:
        self.seed = int(seed)
        self._gen = torch.Generator(device="cpu")
        self._gen.manual_seed(self.seed)
        self._draws = 0

    def reset(self) -> None:
        self._gen.manual_seed(self.seed)
        self._draws = 0

    @property
    def draws(self) -> int:
        """Number of draws taken. Logged so a run's noise consumption is auditable."""
        return self._draws

    def randn_like(self, x: torch.Tensor) -> torch.Tensor:
        self._draws += 1
        n = torch.randn(x.shape, generator=self._gen, dtype=torch.float32)
        return n.to(device=x.device, dtype=x.dtype)

    def rand(self, *shape: int, device: torch.device | str = "cpu") -> torch.Tensor:
        self._draws += 1
        r = torch.rand(*shape, generator=self._gen, dtype=torch.float32)
        return r.to(device=device)
