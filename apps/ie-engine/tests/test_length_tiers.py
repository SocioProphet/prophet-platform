"""Variable-length input coverage for ie-engine (Gap 3 of the Watson-NLU capability-gap audit).

Watson's NLU offerings are documented against richness tiers of roughly 20/50/200 input words —
this file is the harness that was missing to prove ie-engine's extraction doesn't quietly degrade
to empty/garbage output as input length grows (e.g. a truncation bug that zeroes out entity counts
at the longest tier, or a lexicon pass that silently stops matching once a doc gets long).

Each tier below is a strict-superset extension of the previous one (tier200 contains tier50 which
contains tier20), so entity/relation counts are expected to be monotonically non-decreasing across
tiers, and specific entity-sentiment attributions seeded in the 20-word tier ("Apple" positive /
"Boeing" negative) must still resolve correctly once buried inside the 200-word tier.

Sentiment, tone (multi-class emotion), and entity-level sentiment are all hand-built keyword-set
lexicon heuristics (see server.py POS/NEG/EMOTIONS) — NOT trained classifiers. Nothing here asserts
or implies accuracy claims beyond "the lexicon match still fires and isn't clobbered by length."
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]  # apps/ie-engine


def _load_server():
    path = ROOT / "src" / "ie_engine" / "server.py"
    spec = importlib.util.spec_from_file_location("ie_engine_server", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    # dataclasses (and some pydantic setups) on 3.12 resolve cls.__module__ via sys.modules;
    # register before exec_module — same convention as tests/platform_stubs's loader.
    sys.modules["ie_engine_server"] = module
    spec.loader.exec_module(module)
    return module


SERVER = _load_server()

TIER_20 = (
    "Apple reported strong growth this quarter while Boeing faced a major decline in "
    "orders across Europe and Asia this year."
)
TIER_50 = TIER_20 + (
    " Meanwhile investors were furious about the risk at Meta, but pleased with "
    "the success at Google after Sarah Cohen's keynote on July 3, 2026 in San Francisco, "
    "where the board approved a $4.2M compliance budget."
)
TIER_200 = TIER_50 + (
    " Chair Dana Whitfield told the Open Data Governance Board that the European "
    "Commission is expected to align a parallel framework, and analysts said the proposed "
    "rule could raise compliance costs for smaller providers concentrated in Brussels and "
    "Washington. Amazon and Microsoft both disclosed modest gains, while Tesla warned of a "
    "possible penalty tied to an ongoing dispute in Berlin. Employees at the firm expressed "
    "joy over the announced bonus, though some engineers admitted anxiety about the looming "
    "audit scheduled for August. The Federal Trade Commission said it would review the "
    "merger, and a spokesperson for Nvidia noted that demand remained strong despite supply "
    "constraints. Analysts at Morgan Stanley projected continued momentum into the fourth "
    "quarter, citing resilient consumer spending and a rebound in manufacturing output across "
    "the Midwest region. The mood in Brussels turned celebratory after the vote, even as "
    "critics in Washington voiced alarm over the pace of the proposed reforms and their "
    "long-term cost to covered providers."
)
TIERS = {"20": TIER_20, "50": TIER_50, "200": TIER_200}


def test_fixture_word_counts_are_near_their_advertised_tier():
    assert 15 <= len(TIER_20.split()) <= 25
    assert 40 <= len(TIER_50.split()) <= 65
    assert 180 <= len(TIER_200.split()) <= 230


def test_fixtures_are_strict_supersets():
    assert TIER_20 in TIER_50
    assert TIER_50 in TIER_200


@pytest.mark.parametrize("tier", ["20", "50", "200"])
def test_entities_do_not_degrade_to_empty(tier):
    out = SERVER._extract(TIERS[tier])
    assert out["counts"]["entities"] > 0, f"tier {tier}: entity count collapsed to zero"
    assert len(out["entities"]) > 0, f"tier {tier}: entities list is empty"
    # Must actually be real spaCy-typed entities, not just topics/noun-chunks leaking through.
    named = [e for e in out["entities"] if e["type"] != "Topic"]
    assert named, f"tier {tier}: no named entities among {out['entities']}"


@pytest.mark.parametrize("tier", ["20", "50", "200"])
def test_sentiment_lexicon_still_matches(tier):
    out = SERVER._extract(TIERS[tier])
    sentiment = out["sentiment"]
    assert sentiment["label"] in ("positive", "negative", "neutral")
    assert isinstance(sentiment["score"], float)
    # every tier contains "strong"/"growth" (POS) and "decline" (NEG); score must not be a bare 0
    # that would indicate the lexicon pass stopped scanning partway through the doc.
    assert sentiment["score"] != 0.0, f"tier {tier}: sentiment lexicon found no matches at all"


@pytest.mark.parametrize("tier", ["20", "50", "200"])
def test_tone_shape_is_always_present_and_well_formed(tier):
    out = SERVER._extract(TIERS[tier])
    tone = out["tone"]
    assert set(tone["emotions"]) == {"anger", "joy", "sadness", "fear"}
    assert all(isinstance(v, float) for v in tone["emotions"].values())
    assert "heuristic" in tone["method"] and "not a trained" in tone["method"]


@pytest.mark.parametrize("tier", ["50", "200"])
def test_tone_dominant_emotion_fires_once_emotion_words_are_present(tier):
    # TIER_20 deliberately carries no emotion-lexicon words (only polarity words), so it is
    # exercised separately below to confirm that's an honest "no match", not empty/garbage output.
    out = SERVER._extract(TIERS[tier])
    assert out["tone"]["dominant"] is not None, f"tier {tier}: expected an emotion match ('furious')"


def test_tone_dominant_is_honestly_none_when_no_emotion_words_present():
    out = SERVER._extract(TIER_20)
    assert out["tone"]["dominant"] is None
    assert all(v == 0.0 for v in out["tone"]["emotions"].values())


@pytest.mark.parametrize("tier", ["20", "50", "200"])
def test_entity_sentiment_attributes_survive_at_every_length(tier):
    out = SERVER._extract(TIERS[tier])
    by_entity = {row["entity"]: row for row in out["entity_sentiment"]}
    assert by_entity, f"tier {tier}: entity_sentiment is empty"
    # Seeded in TIER_20 and present verbatim in every longer tier — must still resolve correctly
    # even once buried in the middle of the 200-word tier (guards against a truncation/ordering bug).
    assert by_entity["Apple"]["label"] == "positive"
    assert by_entity["Boeing"]["label"] == "negative"
    for row in out["entity_sentiment"]:
        assert row["label"] in ("positive", "negative", "neutral")
        assert row["mentions"] >= 1


def test_entity_counts_do_not_shrink_as_input_grows():
    counts = [SERVER._extract(TIERS[t])["counts"]["entities"] for t in ("20", "50", "200")]
    assert counts == sorted(counts), f"entity counts must be non-decreasing across tiers, got {counts}"
    assert counts[0] > 0 and counts[-1] > counts[0]


def test_extract_endpoint_end_to_end_at_200_words():
    """Same as the direct _extract() checks above, but through the real HTTP contract."""
    client = TestClient(SERVER.app)
    resp = client.post("/extract", json={"text": TIER_200})
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"]["entities"] > 0
    assert body["sentiment"]["label"] in ("positive", "negative", "neutral")
    assert set(body["tone"]["emotions"]) == {"anger", "joy", "sadness", "fear"}
    assert body["entity_sentiment"]
    # response-shape regression guard: existing fields consumed by NlpExtractionBench.vue /
    # SocialSignals.vue in socioprophet-web must still be present (additive-only change).
    for key in ("entities", "relations", "claims", "topics", "sentiment", "counts", "provenance"):
        assert key in body
    assert body["provenance"]["real"] is True
    assert "sentiment_method" in body["provenance"]
