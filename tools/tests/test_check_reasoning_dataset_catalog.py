"""The catalogue gates must bite, and the shipped catalogue must pass them."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_reasoning_dataset_catalog as chk  # noqa: E402

FAMILIES = {"complex_qa.abstention", "argumentation.key_point_prevalence"}


def _entry(**over):
    base = {
        "id": "d", "name": "D", "world": "closed", "family": "f", "availability": "public",
        "tests": ["probes something"],
        "licence": {"name": "CC", "verified": True},
        "use": {"status": "adopted", "rationale": "why", "fixture_families": ["complex_qa.abstention"]},
    }
    base.update(over)
    return {"datasets": [base]}


def test_clean_entry_passes():
    assert chk.violations(_entry(), FAMILIES) == []


def test_adopted_without_verified_licence_is_blocked():
    bad = _entry(licence={"name": "CC", "verified": False})
    assert any("licence.verified" in v for v in chk.violations(bad, FAMILIES))


def test_candidate_with_unverified_licence_is_allowed():
    """Cataloguing is not adopting — an unread licence blocks use, not knowledge."""
    ok = _entry(licence={"name": "CC", "verified": False},
                use={"status": "candidate", "rationale": "why", "fixture_families": []})
    assert chk.violations(ok, FAMILIES) == []


def test_citation_to_a_nonexistent_fixture_family_fails():
    bad = _entry(use={"status": "candidate", "rationale": "why",
                      "fixture_families": ["complex_qa.invented"]})
    assert any("citation to nothing" in v for v in chk.violations(bad, FAMILIES))


def test_missing_required_field_and_duplicate_id_fail():
    payload = _entry()
    del payload["datasets"][0]["world"]
    payload["datasets"].append(dict(payload["datasets"][0]))
    found = chk.violations(payload, FAMILIES)
    assert any("missing required field 'world'" in v for v in found)
    assert any("duplicate dataset id" in v for v in found)


def test_entry_with_no_tests_fails():
    assert any("'tests' is empty" in v for v in chk.violations(_entry(tests=[]), FAMILIES))


def test_selftest_passes():
    assert chk._selftest() == 0


def test_shipped_catalogue_is_clean():
    """The real file, against the real fixture families — not a mock."""
    catalogue = yaml.safe_load(chk.CATALOGUE.read_text(encoding="utf-8"))
    families = chk.known_fixture_families(chk.FIXTURE_DIR)
    assert families, "no fixture families discovered — the grounding check would be vacuous"
    assert chk.violations(catalogue, families) == []


def test_every_dataset_from_the_source_decks_is_present():
    """The point of the exercise: none of these may quietly go missing again."""
    catalogue = yaml.safe_load(chk.CATALOGUE.read_text(encoding="utf-8"))
    ids = {d["id"] for d in catalogue["datasets"]}
    for expected in ["mctest", "squad-v1", "squad-v2", "newsqa", "squad-open", "arc",
                     "snli", "scitail", "arc-knowledge-reasoning-annotations",
                     "key-point-analysis-benchmark", "term-wikifier-mentions"]:
        assert expected in ids, f"{expected} dropped out of the catalogue"
    methods = {m["id"] for m in catalogue["methods"]}
    for expected in ["hope-causality", "gasp", "kpa-method", "term-wikifier"]:
        assert expected in methods, f"{expected} dropped out of the methods list"


def test_undistributed_corpora_are_not_labelled_public_or_adopted():
    """A corpus we cannot obtain must never read as public, nor reach adopted."""
    catalogue = yaml.safe_load(chk.CATALOGUE.read_text(encoding="utf-8"))
    by_id = {d["id"]: d for d in catalogue["datasets"]}
    assert by_id["term-wikifier-mentions"]["availability"] == "not-distributed"
    assert by_id["term-wikifier-mentions"]["use"]["status"] == "not-adopted"


def test_catalogue_carries_no_vendor_attribution():
    """The design is what we keep; nobody's branding rides along in our registry."""
    raw = chk.CATALOGUE.read_text(encoding="utf-8").lower()
    for vendor in ("ibm", "watson"):
        assert vendor not in raw, f"vendor name '{vendor}' leaked into the catalogue"
