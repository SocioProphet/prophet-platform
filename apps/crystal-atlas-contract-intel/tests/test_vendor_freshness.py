"""The vendored semantic library must be exactly what VENDOR.json says it is.

Same discipline as apps/identity-twin: a `source_commit` field is not evidence — the
sha256 of the bytes on disk is. A vendored tree that has drifted from its pin is a fork
wearing a vendor's clothes, and the whole point of consuming this library rather than
reimplementing it is that it stays the proven one.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1]
VENDOR_DIR = APP / "third_party" / "procyber"


def _vendor() -> dict:
    return json.loads((VENDOR_DIR / "VENDOR.json").read_text(encoding="utf-8"))


def test_every_pinned_file_matches_its_hash():
    vendor = _vendor()
    for name, want in vendor["files"].items():
        path = VENDOR_DIR / "semantic" / name
        assert path.exists(), f"{name} is pinned but missing from the vendored tree"
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        assert got == want, f"{name} drifted from its VENDOR.json pin ({got[:12]} != {want[:12]})"


def test_every_vendored_module_is_pinned():
    """The inverse direction: an unpinned file in the tree is unchecked surface."""
    vendor = _vendor()
    on_disk = {p.name for p in (VENDOR_DIR / "semantic").glob("*.py")}
    unpinned = on_disk - set(vendor["files"])
    assert not unpinned, f"vendored but not pinned (drift would go unnoticed): {sorted(unpinned)}"


def test_the_vendored_library_actually_works_here():
    """A pin proves identity, not usability. This proves it runs inside this app."""
    from procyber.semantic.market_paradigm import Claim, MarketMap, reconcile
    from procyber.semantic.semantic_algebra import BOTTOM

    market = MarketMap(axes={"offering": ("a",), "actor": ("x",)})
    market.declare(Claim(cell=("a", "x"), source="s1", value=100.0, unit="u"))
    market.declare(Claim(cell=("a", "x"), source="s2", value=900.0, unit="u"))
    verdict, contradiction = reconcile(market.claims[("a", "x")])
    assert verdict is BOTTOM
    assert contradiction is not None


def test_the_subset_is_minimal_and_self_sufficient():
    """Only what this app calls, and everything it transitively needs."""
    vendor = _vendor()
    assert set(vendor["files"]) == {"__init__.py", "semantic_algebra.py", "market_paradigm.py"}
