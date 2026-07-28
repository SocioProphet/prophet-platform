from __future__ import annotations

import pytest
import torch

from noetica_impair.models import loaders


@pytest.fixture(scope="module")
def toy_dense():
    return loaders.load("toy-dense", seed=1234, device="cpu")


@pytest.fixture(scope="module")
def toy_moe():
    return loaders.load("toy-moe", seed=1234, device="cpu")


@pytest.fixture(scope="module")
def ids():
    g = torch.Generator().manual_seed(7)
    return torch.randint(0, 256, (2, 24), generator=g)
