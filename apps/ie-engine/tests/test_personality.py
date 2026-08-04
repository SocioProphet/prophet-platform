"""Tests for the lexicon-based Big-Five (OCEAN) personality scorer in ie_engine.server.

IMPORTANT — what these tests do and do not prove:
These tests assert that feeding text stereotypically dense in a trait's marker words moves that
trait's score in the expected direction (and, where relevant, that opposite-pole text moves it the
other way). That proves the lexicon look-up and scoring arithmetic behave as designed. It does
NOT and CANNOT prove psychometric validity — there is no labeled ground-truth personality dataset
anywhere in this estate to validate against, and this scorer was never trained or fit to one. This
is a hand-built word-count heuristic (the same category of technique as the POS/NEG sentiment
lexicon already in ie_engine/server.py), being tested for internal consistency only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from ie_engine.server import OCEAN_LEXICON, _personality, app

client = TestClient(app)

OPENNESS_HIGH_TEXT = (
    "I love to imagine new worlds and explore unconventional ideas. Art, philosophy, and abstract "
    "theory fill me with curiosity — I am always eager to discover something novel and inventive."
)
CONSCIENTIOUSNESS_HIGH_TEXT = (
    "I always plan my schedule carefully and organize every task with a detailed checklist. I am "
    "disciplined, punctual, and thorough, and I complete every goal I set with diligent, systematic "
    "preparation."
)
EXTRAVERSION_HIGH_TEXT = (
    "I love a loud party with a big crowd of friends. I am outgoing, energetic, and talkative, "
    "always laughing and chatting at social gatherings — I thrive on excitement with my team."
)
EXTRAVERSION_LOW_TEXT = (
    "I prefer to be alone in quiet solitude. I am reserved, shy, and withdrawn, and I stay silent "
    "and isolated rather than join a gathering."
)
AGREEABLENESS_HIGH_TEXT = (
    "I try to be kind and helpful to everyone. I care about others, share what I have, and feel "
    "compassion and gratitude — I am gentle, polite, and always ready to forgive and cooperate."
)
NEUROTICISM_HIGH_TEXT = (
    "I feel so anxious and worried all the time. I am nervous, afraid, and overwhelmed by stress, "
    "and I often feel sad, lonely, and tense with a sense of dread I cannot shake."
)
NEUTRAL_TEXT = "The quarterly report was filed on Tuesday and sent to the regional office."


def test_healthz_still_ok():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_personality_response_shape_and_disclaimer():
    r = client.post("/personality", json={"text": OPENNESS_HIGH_TEXT})
    assert r.status_code == 200
    body = r.json()
    assert set(body["traits"].keys()) == set(OCEAN_LEXICON.keys())
    for trait, data in body["traits"].items():
        assert 0.0 <= data["score"] <= 1.0
        assert "high_matches" in data and "low_matches" in data and "tokens_considered" in data
    # The honesty framing is not optional — assert it is actually present, in strong terms.
    assert "HEURISTIC" in body["disclaimer"]
    assert "not a trained model" in body["disclaimer"]
    assert "not a validated psychometric instrument" in body["disclaimer"]
    assert body["provenance"]["validated"] is False
    assert "0.5" in body["scale"]


def test_openness_high_text_scores_above_neutral():
    out = _personality(OPENNESS_HIGH_TEXT)
    assert out["traits"]["openness"]["score"] > 0.5
    assert len(out["traits"]["openness"]["high_matches"]) >= 3


def test_conscientiousness_high_text_scores_above_neutral():
    out = _personality(CONSCIENTIOUSNESS_HIGH_TEXT)
    assert out["traits"]["conscientiousness"]["score"] > 0.5
    assert len(out["traits"]["conscientiousness"]["high_matches"]) >= 3


def test_extraversion_direction_flips_between_high_and_low_text():
    high = _personality(EXTRAVERSION_HIGH_TEXT)["traits"]["extraversion"]["score"]
    low = _personality(EXTRAVERSION_LOW_TEXT)["traits"]["extraversion"]["score"]
    assert high > 0.5
    assert low < 0.5
    assert high > low


def test_agreeableness_high_text_scores_above_neutral():
    out = _personality(AGREEABLENESS_HIGH_TEXT)
    assert out["traits"]["agreeableness"]["score"] > 0.5
    assert len(out["traits"]["agreeableness"]["high_matches"]) >= 3


def test_neuroticism_high_text_scores_above_neutral():
    out = _personality(NEUROTICISM_HIGH_TEXT)
    assert out["traits"]["neuroticism"]["score"] > 0.5
    assert len(out["traits"]["neuroticism"]["high_matches"]) >= 3


def test_neutral_text_with_no_marker_words_stays_at_midpoint_for_most_traits():
    out = _personality(NEUTRAL_TEXT)
    # Business-report text carries essentially no OCEAN marker words for most traits, so those
    # traits should sit at (or very near) the 0.5 neutral midpoint — not be pushed to an extreme.
    near_neutral = [t for t, d in out["traits"].items() if abs(d["score"] - 0.5) < 0.05]
    assert len(near_neutral) >= 4


def test_score_saturates_within_bounds_on_extreme_repetition():
    # Pathological input (the same high-marker word repeated) must still clamp to [0, 1], never
    # overshoot — this checks the saturation cap logic, not any claim about real text.
    out = _personality("curious " * 50)
    assert out["traits"]["openness"]["score"] == 1.0
