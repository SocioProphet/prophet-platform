"""The catalog gate has teeth both ways: real breaches VIOLATE, undecidables ZERO, and a ZERO
never rides into the admitted set."""
import json
from pathlib import Path

import pytest

from tools import catalog_invariants as ci

SEED = Path(__file__).resolve().parents[2] / "contracts/crystal-atlas/catalog/prophet_core_catalog_seed.v1.json"


def _e(**over):
    base = {"id": "x", "title": "X", "source_tier": 1, "promotion_state": "adapter_candidate",
            "cache_strategy": "link_only", "mellum_tier": "T2", "license": "CC0-1.0",
            "id_scheme": "s", "access": {"method": "rest"}, "refresh": "live",
            "wall_guard": "public", "upstream": None}
    base.update(over)
    return base


def test_snapshot_with_live_refresh_violates():
    r = ci.inv1_snapshot_pinned(_e(cache_strategy="snapshot_gcs", refresh="live"))
    assert r["verdict"] == ci.VIOLATION


def test_snapshot_with_pinned_refresh_passes():
    assert ci.inv1_snapshot_pinned(_e(cache_strategy="snapshot_gcs", refresh="2026-07-04-hash"))["verdict"] == ci.PASS


def test_copyleft_public_without_attestation_is_zero_not_pass():
    """The invariant's escape hatch is unrecordable -> no test possible. Never a silent pass."""
    r = ci.inv2_obligation_not_public(_e(license="CC-BY-SA-3.0", wall_guard="public"))
    assert r["verdict"] == ci.ZERO


def test_copyleft_public_with_attestation_passes():
    r = ci.inv2_obligation_not_public(
        _e(license="CC-BY-SA-3.0", wall_guard="public", derivative_license_attestation="att:sa/schema-org/1"))
    assert r["verdict"] == ci.PASS


def test_copyleft_non_public_passes():
    assert ci.inv2_obligation_not_public(_e(license="ODbL-1.0", wall_guard="internal"))["verdict"] == ci.PASS


def test_admitted_root_source_is_zero_until_first_party_is_explicit():
    e = _e(promotion_state="admitted", upstream=None)
    assert ci.inv3_admitted_has_provenance(e)["verdict"] == ci.ZERO
    assert ci.inv3_admitted_has_provenance({**e, "first_party": True})["verdict"] == ci.PASS
    assert ci.inv3_admitted_has_provenance({**e, "first_party": False})["verdict"] == ci.VIOLATION


def test_admitted_with_upstream_passes():
    assert ci.inv3_admitted_has_provenance(_e(promotion_state="admitted", upstream="wikidata"))["verdict"] == ci.PASS


def test_restricted_without_grant_is_zero():
    assert ci.inv4_restricted_needs_grant(_e(wall_guard="restricted"))["verdict"] == ci.ZERO
    assert ci.inv4_restricted_needs_grant(_e(wall_guard="restricted", wall_guard_grant="grant:wg/1"))["verdict"] == ci.PASS


def test_nc_admitted_without_gate_is_zero_and_a_prose_note_does_not_satisfy_it():
    e = _e(license="academic-noncommercial", promotion_state="admitted",
           note="NC-academic license => gate commercial")
    assert ci.inv5_nc_needs_commercial_gate(e)["verdict"] == ci.ZERO, "a prose note is not a gate"
    assert ci.inv5_nc_needs_commercial_gate({**e, "commercial_use_gate": "gate:nc/gadm"})["verdict"] == ci.PASS


def test_nc_not_yet_admitted_passes():
    assert ci.inv5_nc_needs_commercial_gate(_e(license="CC-BY-NC-4.0", promotion_state="fixture_only"))["verdict"] == ci.PASS


def test_gate_blocks_zero_on_admitted_but_tolerates_it_on_a_candidate():
    admitted = ci.evaluate({"entries": [_e(id="a", promotion_state="admitted", wall_guard="restricted")]})
    assert any(r["verdict"] == ci.ZERO for r in admitted)
    assert ci.blocked(admitted), "an admitted entry with an undecidable obligation MUST block"

    candidate = ci.evaluate({"entries": [_e(id="c", promotion_state="adapter_candidate", wall_guard="restricted")]})
    assert any(r["verdict"] == ci.ZERO for r in candidate)
    assert not ci.blocked(candidate), "a candidate may carry a known gap"


def test_real_seed_is_evaluated_and_gadm_is_the_worked_case():
    """The shipped seed must stay machine-checkable; gadm's NC gate must remain enforced."""
    seed = json.loads(SEED.read_text())
    results = ci.evaluate(seed)
    assert len(results) == len(seed["entries"]) * len(ci.INVARIANTS)
    gadm = [r for r in results if r["id"] == "gadm" and r["invariant"] == "INV-5"]
    assert gadm and gadm[0]["verdict"] in (ci.ZERO, ci.PASS)
    if gadm[0]["verdict"] == ci.ZERO:
        assert gadm[0] in ci.blocked(results), "an NC source admitted without a gate must block"


def test_every_violation_carries_a_witness():
    """Fail-closed, but never mute: a blocking verdict always says why (INV-F6 discipline)."""
    seed = json.loads(SEED.read_text())
    for r in ci.blocked(ci.evaluate(seed)):
        assert r["witness"] and len(r["witness"]) > 20


def test_seed_conforms_to_the_twelve_governed_fields():
    schema = json.loads((SEED.parents[1] / "schemas/bereshit-catalog-entry.v1.schema.json").read_text())
    assert len(schema["required"]) == 12, "BERESHIT carries exactly twelve governed fields"
    assert "note" not in schema["required"], "prose is never a governed field"
    props = set(schema["properties"])
    for e in json.loads(SEED.read_text())["entries"]:
        assert not set(e) - props, f"{e['id']} has fields outside BERESHIT v1"
        assert not set(schema["required"]) - set(e), f"{e['id']} is missing a governed field"
