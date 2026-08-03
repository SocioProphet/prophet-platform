"""The ontology URIs must EXIST in the TBox this estate actually vendors.

An invented type ref is worse than no type ref: it looks resolvable, so nothing
downstream questions it, and the failure surfaces only when a reasoner is finally
pointed at it. This test reads the vendored KKO TBox from apps/sophos-reasoner and asserts
every URI this service declares is really in it.

It is skipped, loudly, when the TBox is not reachable (an image build that copies only
this app's directory), because a check that silently passes when it cannot look is the
same failure in different clothing.
"""
from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

import pytest

from device_service import contract

#: apps/device-service/tests/test_kko.py -> apps/sophos-reasoner/.../kko-2.10.n3
TBOX = (
    Path(__file__).resolve().parents[2]
    / "sophos-reasoner" / "src" / "sophos_reasoner" / "data" / "kko-2.10.n3"
)

pytestmark = pytest.mark.skipif(
    not TBOX.exists(), reason=f"vendored KKO TBox not reachable at {TBOX}"
)


def _terms() -> set[str]:
    text = TBOX.read_text(encoding="utf-8")
    return set(re.findall(r"(?:^|\s):([A-Za-z][A-Za-z0-9_-]*)", text))


def test_the_declared_kko_uris_exist_in_the_vendored_tbox():
    terms = _terms()
    for uri in (contract.KKO_QUANTITY, contract.KKO_STATES):
        assert uri.startswith(contract.KKO), f"{uri} is not in the KKO namespace"
        local = uri[len(contract.KKO):]
        assert local in terms, (
            f"{uri} is NOT in the vendored KKO TBox ({TBOX.name}). An unresolvable type "
            f"ref that looks resolvable is the silent-wrong this service exists to stop."
        )


def test_every_shipped_profile_cites_only_verified_uris():
    terms = _terms()
    for name in ("virtual-room-sensor", "acme-th100-ble"):
        raw = (resources.files("device_service") / "profiles" / f"{name}.json").read_text("utf-8")
        profile = json.loads(raw)
        for metric in profile["metrics"]:
            uri = metric.get("kkoTypeRef")
            if not uri:
                continue
            assert uri.startswith(contract.KKO), (
                f"{name}/{metric['metric']} cites {uri}, which is outside the vendored "
                f"KKO namespace — the ~58k KBpedia reference-concept layer is NOT "
                f"vendored anywhere in this estate."
            )
            assert uri[len(contract.KKO):] in terms, f"{name}/{metric['metric']}: {uri} not in TBox"


def test_the_specific_reference_concepts_are_confirmed_absent():
    """Documents WHY the typing is coarse, and fails if that ever changes silently: if
    KBpedia reference concepts are vendored later, this test goes red and the profiles
    should be re-typed to the more precise URIs rather than left at Quantity."""
    terms = _terms()
    for tempting in ("Temperature", "RelativeHumidity", "Occupancy"):
        assert tempting not in terms, (
            f"'{tempting}' is now in the vendored TBox — re-type the profiles to the "
            f"precise reference concept instead of the coarse upper-ontology class."
        )
