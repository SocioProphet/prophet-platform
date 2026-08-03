"""Smoke tests for the identity-twin foundation: the vendored ProCybernetica twin library
works inside prophet-platform, and the vendored files match their VENDOR.json pins (no rot)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("cryptography")

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "third_party"))


def test_vendored_files_match_their_pins():
    # Vendor freshness: every vendored file's sha256 must equal the VENDOR.json pin — a drifted
    # vendored copy is the failure class this estate keeps re-discovering.
    vendor = json.loads((APP / "third_party/procyber/VENDOR.json").read_text())
    sem = APP / "third_party/procyber/semantic"
    for fname, want in vendor["files"].items():
        got = hashlib.sha256((sem / fname).read_bytes()).hexdigest()
        assert got == want, f"{fname} drifted from its VENDOR.json pin ({got[:12]} != {want[:12]})"


def test_multiverseal_twin_works_when_vendored():
    import numpy as np

    from procyber.semantic import twin as tw
    from procyber.semantic import vsa

    core = tw.MultiversealTwin(seed=bytes(range(32)))
    value = vsa.random_hv(1024, np.random.default_rng(1))
    ref = core.attest(b"alice#reputation", value)
    assert core.verify(ref) is True
    assert vsa.similarity(core.recall(b"alice#reputation"), value) > 0.99
    snapshot = core.medium().copy()
    core.attest(b"bob#endorsement", vsa.random_hv(1024, np.random.default_rng(2)))
    assert core.is_tampered(snapshot) is True


def test_verifiable_reference_is_unforgeable_when_vendored():
    from procyber.semantic import twin as tw
    from procyber.semantic import vrf

    core = tw.MultiversealTwin(seed=bytes(range(32)))
    forged = vrf.VerifiableReference(b"ctx", b"\x00" * 64, core.verify_key)
    assert core.verify(forged) is False
