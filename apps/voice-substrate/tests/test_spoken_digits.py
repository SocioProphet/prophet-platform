"""Spoken-digit tests — the ASR-specific redaction class.

A text redactor pointed at a transcript misses most numeric PII, because ASR emits
"four one three five five five oh one three four", not "413-555-0134". These pin that the
digit-word path works, that it expands double/triple repeaters, that it survives the mixed
numeric/spoken output real engines produce, and — the part that keeps it usable — that it
does not fire on ordinary speech containing homophones like "to" and "for".
"""
from __future__ import annotations

import pytest

from voice_substrate.redaction import (
    MIN_SPOKEN_DIGITS,
    Redactor,
    RedactionPolicy,
    spoken_number_runs,
)

R = Redactor()


def digits_found(text: str) -> list[int]:
    return [count for _s, _e, count, _l in spoken_number_runs(text)]


# ---------------------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------------------


def test_plain_spoken_digit_run_is_redacted():
    res = R.redact("the number is four one three five five five oh one three four")
    assert res.counts.get("SPOKEN_NUMBER_SEQUENCE") == 1
    assert "four" not in res.text and "five" not in res.text


def test_run_shorter_than_the_threshold_is_left_alone():
    # "one two three" is three digits — a floor number, a countdown, a mic check.
    assert R.redact("okay, one two three, testing").counts == {}


def test_threshold_is_the_shortest_plausible_phone_number():
    assert MIN_SPOKEN_DIGITS == 7
    six = "six five four three two one"
    seven = "six five four three two one nine"
    assert digits_found(six) == []
    assert digits_found(seven) == [7]


def test_double_and_triple_repeaters_expand():
    # "double four" -> 44, so the run is 8 digits from 7 spoken tokens
    assert digits_found("double four seven three one nine two eight") == [8]
    # "triple eight" -> 888, so 5 spoken tokens yield 7 digits
    assert digits_found("triple eight two two two one") == [7]
    # "treble seven" -> 777 and "double two" -> 22: 4 spoken tokens yield 7 digits
    assert digits_found("treble seven double two nine one") == [7]
    # without the repeaters the same token counts fall under the threshold
    assert digits_found("eight two two two one") == []


def test_mixed_numeric_and_spoken_output_is_one_run():
    """Real ASR output for a dictated number is frequently half-normalised."""
    assert digits_found("413 five five five oh one three four") == [10]


def test_oh_and_nought_are_zero():
    assert digits_found("oh seven seven nought nought nine one") == [7]
    assert digits_found("zero seven seven zero zero nine one two") == [8]


def test_separators_do_not_break_a_run():
    for text in [
        "four, one, three, five, five, five, nine",
        "four-one-three-five-five-five-nine",
        "four one three dash five five five nine",
    ]:
        assert digits_found(text) == [7], text


@pytest.mark.parametrize("text", [
    "I have to go for a walk and then eat, too",
    "we need two or three for the meeting",
    "it is for you to decide, one way or another",
])
def test_homophones_never_start_a_run(text):
    """'to'/'too'/'for'/'fore'/'ate' are what ASR emits constantly in ordinary speech.
    They are accepted only as continuations of an already-established digit run, never as
    the token that starts one — without that rule this detector is unusable."""
    assert digits_found(text) == []
    assert R.redact(text).counts == {}


def test_homophones_are_accepted_inside_an_established_run():
    # "five five five to nine one three" — 'to' here is really a 2
    assert digits_found("five five five to nine one three") == [7]


def test_adjacent_written_numbers_do_not_glue_into_a_false_positive():
    """A run must contain at least one genuine digit WORD; otherwise '2026 1500' would be
    an 8-digit 'spoken' sequence. Pure numeric runs are the written-form detectors' job."""
    assert digits_found("in 2026 we shipped 1500 units") == []


def test_a_word_breaks_the_run():
    assert digits_found("four one three please five five five nine") == []


# ---------------------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------------------


def test_spoken_run_that_reconstructs_to_a_luhn_valid_card_is_classified_as_a_card():
    spoken = ("four five three nine one four eight eight oh three four three six four "
              "six seven")  # 4539148803436467
    res = R.redact(f"the card number is {spoken}")
    assert res.counts.get("SPOKEN_CARD_NUMBER") == 1
    assert "SPOKEN_NUMBER_SEQUENCE" not in res.counts


def test_spoken_run_failing_luhn_is_a_generic_sequence_not_a_card():
    spoken = ("four five three nine one four eight eight oh three four three six four "
              "six zero")  # 4539148803436460 — last digit altered
    res = R.redact(f"the reference is {spoken}")
    assert res.counts.get("SPOKEN_NUMBER_SEQUENCE") == 1
    assert "SPOKEN_CARD_NUMBER" not in res.counts


def test_both_spoken_classes_are_still_span_only_in_the_manifest():
    spoken = "four one three five five five oh one three four"
    res = R.redact(f"call {spoken} back")
    assert res.total == 1
    f = res.findings[0]
    assert not hasattr(f, "value") and not hasattr(f, "text")
    assert f.length == f.end - f.start


# ---------------------------------------------------------------------------------------
# Policy knob
# ---------------------------------------------------------------------------------------


def test_threshold_is_configurable_through_the_policy():
    strict = Redactor(RedactionPolicy(min_spoken_digits=4))
    assert strict.redact("code one two three four").counts.get("SPOKEN_NUMBER_SEQUENCE") == 1
    assert R.redact("code one two three four").counts == {}


def test_lowered_threshold_still_classifies_cards_by_luhn():
    strict = Redactor(RedactionPolicy(min_spoken_digits=4))
    spoken = ("four five three nine one four eight eight oh three four three six four "
              "six seven")
    assert strict.redact(spoken).counts.get("SPOKEN_CARD_NUMBER") == 1
