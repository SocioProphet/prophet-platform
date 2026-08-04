"""Redaction tests — per PII class, structural validators, and the no-echo rule.

These run with zero speech dependencies, which is deliberate: redaction is the one stage
that must work in every environment, so its test suite must too.

Every value in this file is synthetic — published test card numbers and IBANs, reserved
phone ranges (07700 900xxx is Ofcom's drama range, 555-01xx is the NANP fictional range),
and never-issued identifier patterns.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from voice_substrate.redaction import (
    COVERED,
    NOT_COVERED,
    POLICY_VERSION,
    Redactor,
    RedactionPolicy,
    iban_ok,
    luhn_ok,
)
from voice_substrate.types import RedactionFinding

R = Redactor()


def types_for(text: str) -> list[str]:
    return [f.type for f in R.scan(text)]


# ---------------------------------------------------------------------------------------
# One test per covered class
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "email me at j.harper@contoso.co.uk please",
    "it's JANE.HARPER+billing@example.com",
    "support@sub.domain.example.org is the alias",
])
def test_email_written(text):
    res = R.redact(text)
    assert res.counts.get("EMAIL") == 1
    assert "@" not in res.text


def test_email_spoken_form():
    # ASR does not emit '@'; this is the form a transcript actually contains.
    res = R.redact("my address is jane dot harper at example dot com")
    assert res.counts.get("EMAIL") == 1
    assert "example" not in res.text


@pytest.mark.parametrize("text,detector_hint", [
    ("call me on +44 20 7946 0958", "international"),
    ("my number is +1 415 555 0132", "international"),
    ("reach me on (413) 555-0134", "nanp"),
    ("dial 413-555-0134 after six", "nanp"),
    ("mobile 07700 900482 is best", "uk"),
    ("the office line is 020 7946 0958", "uk"),
])
def test_phone_formats_international(text, detector_hint):
    res = R.redact(text)
    assert res.counts.get("PHONE") == 1, f"{detector_hint} form not caught: {res.text}"
    assert not any(ch.isdigit() for ch in res.text)


def test_phone_context_gated_form():
    res = R.redact("you can reach me at 415 555 0132 tomorrow")
    assert res.counts.get("PHONE") == 1


def test_credit_card_luhn_valid_is_redacted():
    res = R.redact("the card is 4539 1488 0343 6467 expiring soon")
    assert res.counts.get("CREDIT_CARD") == 1
    assert "4539" not in res.text


def test_credit_card_luhn_invalid_is_not_redacted_as_a_card():
    """The false-positive cut. A 16-digit order reference that fails Luhn must not be
    reported as a card number — otherwise the class is meaningless."""
    res = R.redact("the invoice reference is 4539148803436460 on the PO")
    assert "CREDIT_CARD" not in res.counts


@pytest.mark.parametrize("digits,expected", [
    ("4539148803436467", True),    # published Visa test number
    ("4111111111111111", True),
    ("5500005555555559", True),
    ("378282246310005", True),     # 15-digit Amex
    ("4539148803436460", False),   # last digit altered
    ("1234567812345678", False),
    ("0000000000000000", True),    # degenerate but genuinely Luhn-valid
    ("12345", False),              # too short to be a card
    ("notdigits", False),
])
def test_luhn_checksum(digits, expected):
    assert luhn_ok(digits) is expected


@pytest.mark.parametrize("candidate,expected", [
    ("GB82 WEST 12345698765432", True),
    ("DE89370400440532013000", True),
    ("FR1420041010050500013M02606", True),
    ("GB82 WEST 12345698765433", False),   # check digits broken
    ("GB00 WEST 12345698765432", False),
    ("XX82WEST12345698765432", False),
    ("nonsense", False),
])
def test_iban_mod97(candidate, expected):
    assert iban_ok(candidate) is expected


def test_iban_is_redacted_and_trimmed_to_the_value():
    res = R.redact("send it to GB82 WEST 12345698765432 please")
    assert res.counts.get("IBAN") == 1
    assert res.text == "send it to [REDACTED:IBAN] please"


def test_us_ssn_redacted():
    res = R.redact("my social is 123-45-6789 if you need it")
    assert res.counts.get("NATIONAL_ID") == 1


@pytest.mark.parametrize("bad", [
    "000-45-6789",   # area 000 is never issued
    "666-45-6789",   # area 666 is never issued
    "912-45-6789",   # area 900-999 is never issued
    "123-00-6789",   # group 00 is never issued
    "123-45-0000",   # serial 0000 is never issued
])
def test_ssn_never_issued_ranges_are_not_matched_as_ssn(bad):
    """Issuing-range exclusions are the SSN equivalent of Luhn — without them any
    \\d{3}-\\d{2}-\\d{4} shaped reference gets flagged."""
    findings = [f for f in R.scan(f"the code {bad} is a product sku") if f.detector == "us_ssn"]
    assert findings == []


def test_uk_nino_redacted():
    res = R.redact("my national insurance is QQ 12 34 56 C thanks")
    assert res.counts.get("NATIONAL_ID") >= 1


def test_national_id_cue_gated_redacts_value_not_the_cue():
    res = R.redact("my passport number is X1234567 for the booking")
    assert res.counts.get("NATIONAL_ID") == 1
    # the auditor should still be able to see WHAT was disclosed, just not the value
    assert "passport number" in res.text
    assert "X1234567" not in res.text


def test_date_of_birth_requires_a_birth_cue():
    with_cue = R.redact("I was born on 14/03/1979 in Leeds")
    assert with_cue.counts.get("DATE_OF_BIRTH") == 1
    without_cue = R.redact("the meeting moved to 14/03/1979 apparently")
    assert "DATE_OF_BIRTH" not in without_cue.counts


@pytest.mark.parametrize("text", [
    "date of birth 3 June 1979",
    "DOB: 06/03/1979",
    "her birthday is June 3, 1979",
])
def test_date_of_birth_forms(text):
    assert "DATE_OF_BIRTH" in R.redact(text).counts


def test_redact_all_dates_policy_widens_coverage():
    wide = Redactor(RedactionPolicy(redact_all_dates=True))
    assert "DATE" in wide.redact("the meeting moved to 14/03/1979 apparently").counts


@pytest.mark.parametrize("text", [
    "I live at 221B Baker Street, London",
    "ship to 1600 Pennsylvania Avenue",
    "the depot is at 42 Windmill Lane",
    "post it to PO Box 4471",
    "the postcode is NW1 6XE",
    "our office is in Washington DC 20500",
])
def test_street_address_forms(text):
    assert "STREET_ADDRESS" in R.redact(text).counts


# ---------------------------------------------------------------------------------------
# The no-echo rule — the estate's hard constraint on scanners
# ---------------------------------------------------------------------------------------

SECRETS = [
    "4539 1488 0343 6467",
    "4539148803436467",
    "123-45-6789",
    "j.harper@contoso.co.uk",
    "GB82 WEST 12345698765432",
    "07700 900482",
    "221B Baker Street",
    "14/03/1979",
]
KITCHEN_SINK = (
    "Jane rang from 07700 900482, card 4539 1488 0343 6467, born on 14/03/1979, "
    "SSN 123-45-6789, email j.harper@contoso.co.uk, IBAN GB82 WEST 12345698765432, "
    "lives at 221B Baker Street."
)


def test_finding_dataclass_has_no_field_that_could_hold_a_value():
    """Structural, not behavioural: there is nowhere on RedactionFinding to put the match
    even by accident. Every field is a class label, a detector name, or an integer."""
    fields = {f.name: f.type for f in dataclasses.fields(RedactionFinding)}
    assert set(fields) == {"type", "detector", "start", "end", "length", "segment_index"}
    for name in ("start", "end", "length"):
        assert "int" in fields[name]


def test_manifest_never_echoes_the_removed_value():
    res = R.redact(KITCHEN_SINK)
    manifest_json = json.dumps([dataclasses.asdict(f) for f in res.findings])
    for secret in SECRETS:
        assert secret not in manifest_json
        assert secret.replace(" ", "") not in manifest_json.replace(" ", "")


def test_redacted_text_never_contains_the_removed_value():
    res = R.redact(KITCHEN_SINK)
    for secret in SECRETS:
        assert secret not in res.text
    assert res.total >= 7
    assert res.counts.get("CREDIT_CARD") == 1
    assert res.counts.get("IBAN") == 1


def test_spans_are_offsets_into_the_original_text():
    text = "call 07700 900482 now"
    findings = R.scan(text)
    assert len(findings) == 1
    f = findings[0]
    assert text[f.start:f.end] == "07700 900482"
    assert f.length == f.end - f.start


def test_result_carries_a_digest_and_policy_version_for_the_audit_trail():
    res = R.redact(KITCHEN_SINK)
    assert res.policy_version == POLICY_VERSION
    assert len(res.redacted_sha256) == 64
    assert res.redacted_sha256 == R.redact(KITCHEN_SINK).redacted_sha256


# ---------------------------------------------------------------------------------------
# Overlap resolution and false positives
# ---------------------------------------------------------------------------------------


def test_email_beats_phone_on_an_address_containing_digits():
    assert types_for("write to user4155550132@example.com today") == ["EMAIL"]


def test_luhn_valid_run_is_a_card_not_a_phone():
    assert "CREDIT_CARD" in types_for("the number 4539148803436467 is on the account")


def test_no_overlapping_spans_are_ever_emitted():
    findings = R.scan(KITCHEN_SINK)
    for a, b in zip(findings, findings[1:]):
        assert a.end <= b.start


@pytest.mark.parametrize("ordinary", [
    "I have to go for a walk in about ten minutes",
    "we shipped 1500 units in 2026, up from 900",
    "meet me on the second floor at four o'clock",
    "the release is version 3.12.1 and the build is 4471",
    "one two three, testing the microphone",
])
def test_no_false_positives_on_ordinary_speech(ordinary):
    assert R.redact(ordinary).counts == {}


def test_empty_and_whitespace_input():
    assert R.redact("").text == ""
    assert R.redact("   ").counts == {}


# ---------------------------------------------------------------------------------------
# Declared policy
# ---------------------------------------------------------------------------------------


def test_policy_declares_both_what_is_covered_and_what_is_not():
    covered_types = {c["type"] for c in COVERED}
    assert {"EMAIL", "PHONE", "CREDIT_CARD", "IBAN", "NATIONAL_ID", "DATE_OF_BIRTH",
            "STREET_ADDRESS", "SPOKEN_NUMBER_SEQUENCE"} <= covered_types
    gaps = {g["gap"] for g in NOT_COVERED}
    # the honesty items that must never be quietly dropped from the policy
    assert "the audio itself" in gaps
    assert "measured precision/recall" in gaps
    assert any("quasi-identifier" in g for g in gaps)


def test_no_accuracy_number_is_claimed_anywhere_in_the_policy():
    blob = json.dumps({"covered": list(COVERED), "not_covered": list(NOT_COVERED)}).lower()
    for forbidden in ("% precision", "% recall", "f1 of", "wer of", "der of", "accuracy of"):
        assert forbidden not in blob


def test_every_active_detector_maps_to_a_declared_covered_type():
    declared = {c["type"] for c in COVERED} | {"DATE"}
    for det in Redactor(RedactionPolicy(redact_all_dates=True)).active_detectors:
        assert det["type"] in declared, f"undeclared redaction type: {det['type']}"
