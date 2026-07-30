"""The contract layer: vendoring integrity, digest pinning, and the attribution gate.

The negative cases here are the point. A gate that only ever sees conforming input has
not been tested; it has been visited.
"""
from __future__ import annotations

import copy
import hashlib
import json
from importlib import resources

import pytest
from jsonschema import Draft202012Validator

from device_service import contract


# ------------------------------------------------------------------ vendoring
def test_vendored_schema_hashes_match_the_pins():
    for name, pinned in (
        ("DeviceProfile.json", contract.PROFILE_SCHEMA_SHA256),
        ("DeviceReading.json", contract.READING_SCHEMA_SHA256),
        ("NullAbsenceRecord.json", contract.ABSENCE_SCHEMA_SHA256),
    ):
        raw = (resources.files("device_service") / "schemas" / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == pinned, f"{name} drifted from its pin"


def test_schemas_are_valid_2020_12_documents():
    for schema in (contract.PROFILE_SCHEMA, contract.READING_SCHEMA, contract.ABSENCE_SCHEMA):
        Draft202012Validator.check_schema(schema)


def test_date_time_format_checking_is_actually_wired():
    """Without rfc3339-validator the date-time checker is a silent no-op, and every
    timestamp in the family goes unvalidated. contract.py refuses to import in that
    state; this proves the checker is live rather than merely passed."""
    assert "date-time" in Draft202012Validator.FORMAT_CHECKER.checkers
    bad = {"observedAt": "not-a-timestamp"}
    errors = list(contract.READING_VALIDATOR.iter_errors({**bad}))
    assert any("not-a-timestamp" in e.message or "date-time" in e.message for e in errors)


# --------------------------------------------------------------------- digest
def test_definition_digest_matches_the_profile_as_written(virtual_profile):
    assert virtual_profile["definitionDigest"] == contract.definition_digest(virtual_profile)


def test_digest_algorithm_is_the_normative_one(virtual_profile):
    core = {f: virtual_profile[f] for f in ["deviceClass", "protocol", "metrics"]}
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert contract.definition_digest(virtual_profile) == expected


def test_widening_a_range_changes_the_digest(virtual_profile):
    """THE attack this construct exists to stop: a reading fails the declared range, so
    somebody widens the range. The digest must move, orphaning the readings that pinned
    the old one instead of retroactively legalising them."""
    before = contract.definition_digest(virtual_profile)
    widened = copy.deepcopy(virtual_profile)
    widened["metrics"][0]["maximum"] = 200.0
    assert contract.definition_digest(widened) != before


def test_prose_edits_do_not_change_the_digest(virtual_profile):
    """The converse: a documentation change must NOT orphan live readings."""
    before = contract.definition_digest(virtual_profile)
    edited = copy.deepcopy(virtual_profile)
    edited["manufacturer"] = "Someone Else"
    edited["declaredAt"] = "2027-01-01T00:00:00.000Z"
    edited["policyLabels"] = edited["policyLabels"] + ["extra:label"]
    assert contract.definition_digest(edited) == before


def test_load_profile_refuses_a_lying_digest(virtual_profile):
    lying = copy.deepcopy(virtual_profile)
    lying["definitionDigest"] = "sha256:" + "0" * 64
    with pytest.raises(contract.ContractError, match="not the digest of its own"):
        contract.load_profile(lying)


def test_load_profile_refuses_duplicate_metric_names(virtual_profile):
    dupe = copy.deepcopy(virtual_profile)
    dupe["metrics"].append(copy.deepcopy(dupe["metrics"][0]))
    dupe["definitionDigest"] = contract.definition_digest(dupe)
    with pytest.raises(contract.ContractError, match="duplicate metric"):
        contract.load_profile(dupe)


# ---------------------------------------------------------------- attribution
def test_a_built_reading_is_attributable(reading, virtual_profile):
    contract.validate_reading(reading, virtual_profile)
    for key in ("deviceRef", "deviceProfileRef", "profileDigest", "metric",
                "sourceAddress", "unit", "quality", "observedAt"):
        assert reading[key], f"{key} must be present and non-empty"


def test_the_builder_copies_attribution_from_the_profile_not_the_caller(reading, virtual_profile):
    """A driver reports a value; it cannot supply the fields that give it meaning."""
    declared = contract.metric_of(virtual_profile, "temperature")
    assert reading["unit"] == declared["unit"]
    assert reading["sourceAddress"] == declared["sourceAddress"]
    assert reading["kkoTypeRef"] == declared["kkoTypeRef"]
    assert reading["profileDigest"] == virtual_profile["definitionDigest"]


def test_provenance_links_name_both_the_device_and_the_profile(reading):
    refs = {link["ref"] for link in reading["provenanceLinks"]}
    assert reading["deviceRef"] in refs
    assert reading["deviceProfileRef"] in refs


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("unit", "[degF]", "contradicts the declared"),
        ("sourceAddress", "virtual://room-sensor/humidity.relative", "not the channel declared"),
        ("profileDigest", "sha256:" + "1" * 64, "recomputed digest"),
        ("deviceProfileRef", "urn:srcos:device-profile:someone_else", "validated against"),
        ("kkoTypeRef", "http://example.org/Nope", "kkoTypeRef disagrees"),
    ],
)
def test_attribution_drift_is_refused(reading, virtual_profile, mutate, field, value, match):
    with pytest.raises(contract.ContractError, match=match):
        contract.validate_reading(mutate(reading, **{field: value}), virtual_profile)


def test_value_outside_the_declared_range_is_refused(reading, virtual_profile, mutate):
    with pytest.raises(contract.ContractError, match="outside the declared operating range"):
        contract.validate_reading(mutate(reading, value=900.0), virtual_profile)


def test_value_of_the_wrong_declared_type_is_refused(reading, virtual_profile, mutate):
    with pytest.raises(contract.ContractError, match="not the declared number"):
        contract.validate_reading(mutate(reading, value="21.5"), virtual_profile)


def test_undeclared_metric_is_refused(reading, virtual_profile, mutate):
    with pytest.raises(contract.ContractError, match="not declared by"):
        contract.validate_reading(mutate(reading, metric="pressure"), virtual_profile)


def test_received_before_observed_is_refused(reading, virtual_profile, mutate):
    with pytest.raises(contract.ContractError, match="receivedAt precedes observedAt"):
        contract.validate_reading(
            mutate(reading, receivedAt="2026-07-29T09:14:00.000Z"), virtual_profile
        )


# ------------------------------------------------- instants, not strings (§6)
#
# DeviceReading pins `format: date-time` with NO `pattern`, so schema-valid stamps vary
# in UTC offset AND fractional-second precision. The pairs below are the ones a
# string comparison gets WRONG. They are not hypothetical: both were verified against
# the identical check in sourceos-spec before this fix landed.
#
# (observedAt, receivedAt, how much earlier receivedAt actually is)
INVERTED_PAIRS_THAT_SORT_FORWARD = [
    # '.' (0x2E) < 'Z' (0x5A): the more precise stamp sorts FIRST while being later.
    ("2026-07-29T09:15:00.500Z", "2026-07-29T09:15:00Z", "0.5s"),
    # "21" > "20" as text, but +05:00 puts 21:00 at 16:00Z — four hours before.
    ("2026-07-29T20:00:00+00:00", "2026-07-29T21:00:00+05:00", "4h"),
]

# Positive controls: genuinely well-ordered pairs, written across offsets and
# precisions, that MUST still be admitted. A stricter gate that refuses good readings
# has just moved the bug.
ORDERED_PAIRS_ACROSS_OFFSETS_AND_PRECISIONS = [
    # Same instant, two spellings. Equal is admissible (the invariant is >=).
    ("2026-07-29T09:15:00Z", "2026-07-29T11:15:00+02:00"),
    # 42ms of real latency; '.042Z' sorts BEFORE 'Z', so string compare false-alarms.
    ("2026-07-29T09:15:00Z", "2026-07-29T09:15:00.042Z"),
    # 1s of real latency across a +02:00 offset.
    ("2026-07-29T20:00:00+00:00", "2026-07-29T22:00:01+02:00"),
]

# The one positive control that a string comparison actively REJECTS. Teeth have to
# point both ways: a gate that only false-negatives is blind, one that false-positives
# throws away good readings. This pair proves the fix fixes the second failure too.
STRING_COMPARE_FALSE_ALARM = ("2026-07-29T09:15:00Z", "2026-07-29T09:15:00.042Z")


@pytest.mark.parametrize("observed,received,gap", INVERTED_PAIRS_THAT_SORT_FORWARD)
def test_inverted_pair_is_refused_even_when_it_sorts_forward(
    reading, virtual_profile, mutate, observed, received, gap
):
    """THE regression. receivedAt is genuinely earlier by {gap}; the old
    `reading["receivedAt"] < reading["observedAt"]` string compare said otherwise and
    admitted the reading."""
    with pytest.raises(contract.ContractError, match="receivedAt precedes observedAt"):
        contract.validate_reading(
            mutate(reading, observedAt=observed, receivedAt=received, wallTime=received),
            virtual_profile,
        )


@pytest.mark.parametrize("observed,received", ORDERED_PAIRS_ACROSS_OFFSETS_AND_PRECISIONS)
def test_equivalent_instants_written_differently_are_admitted(
    reading, virtual_profile, mutate, observed, received
):
    """Positive control: correctly-ordered pairs across offsets and precisions must
    still PASS. A gate that refuses these has moved the bug, not fixed it."""
    contract.validate_reading(
        mutate(reading, observedAt=observed, receivedAt=received, wallTime=received),
        virtual_profile,
    )


def test_the_counterexamples_are_actually_adversarial():
    """Guards the guard. If a future edit weakened these fixtures into pairs a string
    compare already handles, the tests above would still be green while testing
    nothing. This asserts, explicitly, that naive `<` gets them wrong — so the cases
    keep their teeth even if the fix is reverted and re-derived."""
    for observed, received, _gap in INVERTED_PAIRS_THAT_SORT_FORWARD:
        assert contract.instant(received) < contract.instant(observed), "not inverted"
        assert not (received < observed), "a string compare would already catch this"
    for observed, received in ORDERED_PAIRS_ACROSS_OFFSETS_AND_PRECISIONS:
        assert contract.instant(received) >= contract.instant(observed), "not ordered"

    observed, received = STRING_COMPARE_FALSE_ALARM
    assert (observed, received) in ORDERED_PAIRS_ACROSS_OFFSETS_AND_PRECISIONS
    assert received < observed, "this control no longer false-alarms a string compare"


@pytest.mark.parametrize("text,expected", [
    ("2026-07-29T09:15:00Z", "2026-07-29 09:15:00+00:00"),
    ("2026-07-29T09:15:00.500Z", "2026-07-29 09:15:00.500000+00:00"),
    ("2026-07-29t09:15:00z", "2026-07-29 09:15:00+00:00"),      # RFC3339 lowercase
    ("2026-07-29T11:15:00+02:00", "2026-07-29 09:15:00+00:00"),  # normalised to UTC
    ("2026-07-29T21:00:00+05:00", "2026-07-29 16:00:00+00:00"),
])
def test_instant_normalises_to_utc(text, expected):
    assert str(contract.instant(text)) == expected


@pytest.mark.parametrize("text", [
    "2026-07-29T09:15:00",   # naive: RFC3339 requires an offset
    "2026-07-29",            # a date is not an instant
    "yesterday",
    "",
])
def test_instant_fails_closed_on_anything_that_is_not_an_instant(text):
    """A naive stamp carries no offset, so it is not an instant — refuse it rather than
    assume UTC and silently compare two different clocks."""
    assert contract.instant(text) is None


def test_a_reading_with_no_receivedAt_is_admitted(reading, virtual_profile):
    """receivedAt is optional in DeviceReading.json (not in `required`). The check now
    reads it with .get() like the spec tool does; the old `reading["receivedAt"]` raised
    a bare KeyError — not a ContractError — on a schema-valid reading that omits it, so
    the caller's `except ContractError` would not have counted it as a validation
    failure. There is nothing to order here, and nothing to fail."""
    without = {k: v for k, v in reading.items() if k != "receivedAt"}
    contract.validate_reading(without, virtual_profile)


def test_an_unorderable_pair_is_refused_not_waved_through(
    reading, virtual_profile, mutate, monkeypatch
):
    """Defence in depth. The schema's date-time format checker normally rejects a naive
    stamp first (contract.py refuses to import without it). If that layer ever degraded,
    the ordering gate must still refuse the pair it cannot order — never pass it."""
    monkeypatch.setattr(
        contract, "READING_VALIDATOR", Draft202012Validator(contract.READING_SCHEMA)
    )
    with pytest.raises(contract.ContractError, match="unorderable pair"):
        contract.validate_reading(
            mutate(reading, observedAt="2026-07-29T09:15:00", receivedAt="2026-07-29T09:15:01"),
            virtual_profile,
        )


def test_schema_violations_are_refused(reading, virtual_profile, mutate):
    with pytest.raises(contract.ContractError, match="schema"):
        contract.validate_reading(mutate(reading, specVersion="0.2.0"), virtual_profile)
    with pytest.raises(contract.ContractError, match="schema"):
        contract.validate_reading(mutate(reading, quality="estimated"), virtual_profile)
    with pytest.raises(contract.ContractError, match="schema"):
        contract.validate_reading(mutate(reading, observedAt="yesterday"), virtual_profile)


# ------------------------------------------------------- simulated visibility
def test_a_simulated_reading_carries_its_labels(reading):
    assert contract.SIMULATED_LABEL in reading["policyLabels"]
    assert contract.SIMULATED_RISK in reading["riskLabels"]


def test_stripping_the_simulated_label_is_refused(reading, virtual_profile, mutate):
    with pytest.raises(contract.ContractError, match="visibly distinguishable"):
        contract.validate_reading(mutate(reading, policyLabels=[]), virtual_profile)


def test_a_physical_reading_may_not_claim_to_be_simulated(ble_profile):
    physical = contract.build_reading(
        profile=ble_profile,
        device_ref="urn:srcos:device:th100_bed2",
        metric="temperature",
        value=21.0,
        quality="ok",
        observed_at="2026-07-29T09:15:00.000Z",
        received_at="2026-07-29T09:15:00.100Z",
        wall_time="2026-07-29T09:15:00.100Z",
        logical_time=1,
        sequence_ref=1,
        workspace_ref="urn:srcos:workspace:citizen_home_demo",
        branch_ref="urn:srcos:branch:home_main",
        actor_ref="urn:srcos:agent:device_service",
    )
    assert contract.SIMULATED_LABEL not in physical["policyLabels"]
    contract.validate_reading(physical, ble_profile)
    physical["policyLabels"] = [contract.SIMULATED_LABEL]
    with pytest.raises(contract.ContractError, match="must not be labelled simulated"):
        contract.validate_reading(physical, ble_profile)


# ------------------------------------------------------------- typed absence
def _absent(profile, **over):
    base = dict(
        profile=profile,
        device_ref="urn:srcos:device:room_sensor_01",
        metric="temperature",
        value=None,
        quality="unavailable",
        observed_at="2026-07-29T09:15:00.000Z",
        received_at="2026-07-29T09:15:00.042Z",
        wall_time="2026-07-29T09:15:00.042Z",
        logical_time=200,
        sequence_ref=200,
        workspace_ref="urn:srcos:workspace:citizen_home_demo",
        branch_ref="urn:srcos:branch:home_main",
        actor_ref="urn:srcos:agent:device_service",
    )
    base.update(over)
    return contract.build_reading(**base)


def test_an_absence_is_typed_end_to_end(virtual_profile):
    reading_id = "urn:srcos:device-reading:" + contract.reading_local_id(
        "urn:srcos:device:room_sensor_01", "temperature", 200
    )
    record = contract.build_absence_record(
        reading_id=reading_id, kind="timeout", observed_at="2026-07-29T09:15:00.000Z",
        workspace_ref="urn:srcos:workspace:citizen_home_demo",
        branch_ref="urn:srcos:branch:home_main",
        device_ref="urn:srcos:device:room_sensor_01", metric="temperature",
        expected_next_sequence=201, causal_notes="no notification in the window",
    )
    reading = _absent(virtual_profile, null_absence_ref=record["id"])
    contract.validate_reading(reading, virtual_profile)
    contract.validate_absence_record(record, reading)
    assert reading["value"] is None
    assert record["kind"] == "timeout"


def test_an_untyped_absence_is_refused_by_the_schema(virtual_profile):
    with pytest.raises(contract.ContractError, match="schema"):
        contract.validate_reading(_absent(virtual_profile), virtual_profile)


def test_an_absence_carrying_a_value_is_refused(virtual_profile):
    reading = _absent(virtual_profile, null_absence_ref="urn:srcos:null-absence:x")
    reading["value"] = 21.0
    with pytest.raises(contract.ContractError, match="schema"):
        contract.validate_reading(reading, virtual_profile)


def test_a_driver_may_not_assert_intent_it_cannot_observe():
    """`intentional_silence` and `refusal` are claims about a device's intent. A
    southbound driver has no basis for either; asserting one would be inventing a cause."""
    for kind in ("intentional_silence", "refusal", "withheld_redacted"):
        with pytest.raises(contract.ContractError, match="not one a southbound driver"):
            contract.build_absence_record(
                reading_id="urn:srcos:device-reading:x", kind=kind,
                observed_at="2026-07-29T09:15:00.000Z", workspace_ref="w", branch_ref="b",
                device_ref="urn:srcos:device:d", metric="temperature",
                expected_next_sequence=1, causal_notes="n",
            )


def test_a_dangling_absence_reference_is_refused(virtual_profile):
    reading = _absent(virtual_profile, null_absence_ref="urn:srcos:null-absence:wrong_one")
    record = contract.build_absence_record(
        reading_id=reading["id"], kind="timeout", observed_at="2026-07-29T09:15:00.000Z",
        workspace_ref="w", branch_ref="b", device_ref="urn:srcos:device:room_sensor_01",
        metric="temperature", expected_next_sequence=201, causal_notes="n",
    )
    with pytest.raises(contract.ContractError, match="does not name this absence record"):
        contract.validate_absence_record(record, reading)


# ------------------------------------------------------------- misc contract
def test_reading_ids_are_deterministic():
    a = contract.reading_local_id("urn:srcos:device:room_sensor_01", "humidity.relative", 7)
    b = contract.reading_local_id("urn:srcos:device:room_sensor_01", "humidity.relative", 7)
    assert a == b
    assert a != contract.reading_local_id("urn:srcos:device:room_sensor_02", "humidity.relative", 7)


def test_reading_ids_satisfy_the_urn_pattern(virtual_profile, reading):
    import re

    pattern = contract.READING_SCHEMA["properties"]["id"]["pattern"]
    assert re.match(pattern, reading["id"])


def test_flatten_carries_the_whole_validated_object(reading):
    flat = contract.flatten(reading, ingest_time="2026-07-29T09:15:01.000Z")
    assert json.loads(flat["reading"]) == reading
    assert flat["valueNum"] == reading["value"]
    assert flat["simulated"] is True


def test_batch_hash_binds_every_byte(reading, mutate):
    a = contract.batch_hash([reading])
    assert a == contract.batch_hash([reading])
    assert a != contract.batch_hash([mutate(reading, value=21.51)])
    assert a != contract.batch_hash([reading, reading])


def test_startup_check_passes_for_shipped_profiles(virtual_profile, ble_profile):
    contract.startup_check([virtual_profile, ble_profile])


def test_startup_check_fails_on_a_tampered_profile(virtual_profile):
    tampered = copy.deepcopy(virtual_profile)
    tampered["metrics"][0]["unit"] = "[degF]"  # digest no longer matches
    with pytest.raises(contract.ContractError):
        contract.startup_check([tampered])
