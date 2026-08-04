"""The Crystal Atlas README must name exactly the event schemas that ship.

Found drifting in both directions at once: three families were documented with no
schema behind them (something could be built against a contract that does not exist),
and five schemas shipped undocumented — including `intel.value_driver.scored.v0`, the
one the market bridge consumes. A register that is wrong in both directions is worse
than no register, because it is still believed.

Planned work stays expressible: an entry marked _(planned)_ is intent and is exempt
from needing a schema. What it may not do is look like a contract.
"""

from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
EVENTS = REPO / "contracts/crystal-atlas/events"
README = REPO / "contracts/crystal-atlas/README.md"

_ENTRY = re.compile(r"^- `([a-z]+(?:\.[a-z_]+)+\.v\d+)`(\s*_\(planned\)_)?", re.MULTILINE)


def _shipped() -> set[str]:
    return {p.name.replace(".schema.json", "") for p in EVENTS.glob("*.schema.json")}


def _documented() -> tuple[set[str], set[str]]:
    contracted, planned = set(), set()
    for name, marker in _ENTRY.findall(README.read_text(encoding="utf-8")):
        (planned if marker else contracted).add(name)
    return contracted, planned


def test_the_register_is_not_empty():
    """A vacuous register would make every assertion below trivially true."""
    assert _shipped(), "no event schemas found"
    contracted, _ = _documented()
    assert contracted, "README lists no contracted event families"


def test_every_documented_contract_has_a_schema():
    contracted, _ = _documented()
    missing = contracted - _shipped()
    assert not missing, (
        "documented as contract but no schema ships — mark _(planned)_ or add the "
        f"schema: {sorted(missing)}"
    )


def test_every_shipped_schema_is_documented():
    contracted, planned = _documented()
    undocumented = _shipped() - contracted - planned
    assert not undocumented, (
        f"schema ships but the README never mentions it: {sorted(undocumented)}"
    )


def test_planned_entries_do_not_have_schemas():
    """If it shipped, it is no longer planned — the marker must come off."""
    _, planned = _documented()
    landed = planned & _shipped()
    assert not landed, f"marked _(planned)_ but the schema ships; drop the marker: {sorted(landed)}"
