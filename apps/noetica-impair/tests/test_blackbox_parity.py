"""Measuring a black box on the same standard as a white box.

The trap this guards: a black box that cannot expose logprobs must be scored by
generation. If its white-box reference were scored by logprob, the comparison would be
between INSTRUMENTS rather than between models — while looking perfectly rigorous.
"""

from __future__ import annotations

import pytest

from noetica_impair.drivers.blackbox import (
    BlackBoxDriver, BlackBoxError, BlackBoxSubject,
)
from noetica_impair.models import pairing
from noetica_impair.probes.base import (
    choose, common_scoring_mode, scoring_modes,
)
from noetica_impair.readout.invariance import (
    check_invariance, read_black_box,
)
from noetica_impair.readout.metrics import FacultyVector


class WhiteBox:
    """A subject with both instruments available."""
    def generate(self, prompt, *, max_new_tokens=64):
        return "A"
    def loglikelihood(self, prompt, continuation):
        return 0.0 if "seven" in continuation else -5.0


def api(reply="A"):
    return BlackBoxSubject(complete=lambda p, n: reply, model_id="test-api")


# ── instrument parity ────────────────────────────────────────────────────────

def test_black_box_declares_only_the_generative_instrument():
    assert scoring_modes(api()) == ("generative",)


def test_white_box_prefers_logprob_alone():
    assert scoring_modes(WhiteBox())[0] == "logprob"


def test_a_pair_negotiates_down_to_the_shared_instrument():
    """The reference is deliberately measured less precisely, so the pair is fair."""
    assert common_scoring_mode(WhiteBox(), api()) == "generative"


def test_negotiation_records_that_the_reference_was_downgraded():
    d = BlackBoxDriver(api())
    mode = d.negotiate_with(WhiteBox())
    assert mode == "generative"
    assert any("less precisely" in n for n in d.notes), d.notes


def test_no_shared_instrument_is_an_error_not_a_silent_pick():
    class Weird:
        supported_scoring_modes = ()
    with pytest.raises(ValueError, match="no shared scoring mode"):
        common_scoring_mode(WhiteBox(), Weird())


def test_logprob_on_a_provider_without_them_refuses_loudly():
    s = api()
    with pytest.raises(BlackBoxError, match="does not expose logprobs"):
        s.loglikelihood("q", "a")


# ── no dose on a black box ───────────────────────────────────────────────────

def test_black_box_refuses_a_mechanical_dose():
    """A run that looked dosed but was not would corrupt every comparison it entered."""
    d = BlackBoxDriver(api())
    with pytest.raises(BlackBoxError, match="has no .*hooks|cannot apply dose"):
        d.subject(0.4)


def test_black_box_allows_the_sober_subject():
    d = BlackBoxDriver(api())
    assert d.subject(0.0) is d.subject_impl


def test_describe_states_that_no_hooks_exist():
    d = BlackBoxDriver(api())
    info = d.describe()
    assert info["hooks_installed"] is False
    assert info["mechanical_dose_possible"] is False


# ── generative forced choice ─────────────────────────────────────────────────

def test_generative_choice_parses_a_letter():
    picked = {}
    def complete(prompt, n):
        # answer whichever letter is on the line containing "seven"
        for line in prompt.splitlines():
            if "seven" in line:
                picked["line"] = line
                return line.strip()[0]
        return "A"
    s = BlackBoxSubject(complete=complete, model_id="m")
    idx = choose(s, "Nine minus two equals", [" seven", " four"], mode="generative")
    assert idx == 0


def test_generative_choice_permutes_option_order():
    """A fixed order lets position bias masquerade as competence."""
    seen = []
    def complete(prompt, n):
        seen.append([l for l in prompt.splitlines() if l.startswith("A.")][0])
        return "A"
    s = BlackBoxSubject(complete=complete, model_id="m")
    for item in range(12):
        choose(s, "q", [" alpha", " beta"], mode="generative", seed=1, item_id=item)
    assert len(set(seen)) > 1, "option A was always the same string — no permutation"


def test_unparseable_reply_is_not_a_valid_choice():
    s = BlackBoxSubject(complete=lambda p, n: "I cannot answer that", model_id="m")
    assert choose(s, "q", [" a", " b"], mode="generative") == -1


# ── the vendor pairing registry ──────────────────────────────────────────────

def test_openai_pairs_with_its_own_open_weights():
    p = pairing.get("gpt-5")          # prefix match onto "gpt"
    assert p.reference_hf_id == "openai/gpt-oss-20b"
    assert p.kinship == "same_lab_open_weights"
    assert not p.weakly_calibrated


def test_google_pairs_with_gemma_and_has_sae():
    p = pairing.get("gemini")
    assert p.reference_key == "gemma2-9b"
    assert p.has_sae, "Gemma Scope is what lets the reference ladder include steering"


def test_anthropic_has_no_open_weight_reference():
    """Stated plainly rather than substituting a convenient ruler."""
    p = pairing.get("claude")
    assert p.reference_key is None
    assert p.kinship == "none_available"
    assert p.weakly_calibrated
    assert "not released open-weight" in p.rationale.lower() or \
           "has not released" in p.rationale.lower()


def test_unknown_target_is_unrelated_not_a_guess():
    p = pairing.get("some-new-model")
    assert p.kinship == "unrelated" and p.reference_key is None


# ── invariance ───────────────────────────────────────────────────────────────

def sig(**kw):
    return FacultyVector(**{**{f: 1.0 for f in
                              ("consistency", "calibration", "lookahead",
                               "working_memory", "fluency", "competence")}, **kw})


def test_a_consistent_signature_across_labs_is_transportable():
    per_model = {
        "gemma2-9b": sig(competence=0.5, working_memory=0.4, fluency=0.95),
        "gpt-oss-20b": sig(competence=0.55, working_memory=0.45, fluency=0.93),
        "mixtral-8x7b": sig(competence=0.52, working_memory=0.42, fluency=0.96),
    }
    r = check_invariance("charged-topic-A", per_model)
    assert r.invariant, r.report()
    assert r.transportable


def test_a_pipeline_specific_signature_is_not_transportable():
    """Models disagreeing about WHICH faculty is hit means the ladder is not shared."""
    per_model = {
        "gemma2-9b": sig(competence=0.4, working_memory=0.95),
        "gpt-oss-20b": sig(competence=0.95, working_memory=0.4),
        "mixtral-8x7b": sig(competence=0.7, working_memory=0.7, fluency=0.4),
    }
    r = check_invariance("charged-topic-B", per_model)
    assert not r.invariant
    assert not r.transportable


def test_too_few_models_cannot_establish_invariance():
    r = check_invariance("x", {"gemma2-9b": sig(competence=0.5)})
    assert not r.invariant
    assert any("cannot distinguish" in w for w in r.warnings)


def test_reading_without_invariance_is_not_defensible():
    r = read_black_box(target="claude", condition="topic-A", faculty=sig(competence=0.6),
                       invariance=None, kinship="none_available",
                       scoring_mode="generative")
    assert not r.defensible
    assert any("no invariance check" in c for c in r.caveats)


def test_a_defensible_reading_still_carries_the_behavioural_caveat():
    per_model = {
        "gemma2-9b": sig(competence=0.5, working_memory=0.4),
        "gpt-oss-20b": sig(competence=0.53, working_memory=0.43),
        "mixtral-8x7b": sig(competence=0.51, working_memory=0.41),
    }
    inv = check_invariance("topic-A", per_model)
    r = read_black_box(target="claude", condition="topic-A", faculty=sig(competence=0.55),
                       invariance=inv, kinship="none_available",
                       scoring_mode="generative",
                       reference_models=list(per_model))
    assert r.defensible, r.report()
    assert any("BEHAVIOURAL ONLY" in c for c in r.caveats)
    assert any("another lab" in c for c in r.caveats)


@pytest.mark.parametrize("reply,expected", [
    ("B", 1), ("a", 0), (" b.", 1), ("Answer: B", 1), ("The answer is B", 1),
    ("B) beta", 1),
    # refusals and hedges must NOT parse as a choice
    ("I cannot answer that", -1),      # the A inside CANNOT
    ("As an AI, no", -1),
    ("I refuse to comply", -1),
    ("", -1),
])
def test_choice_parsing_accepts_answers_and_rejects_refusals(reply, expected):
    """Regression: 'I cannot answer that' parsed as option A, because of the A inside
    CANNOT. A refusal scored as an answer would corrupt refusal_guard — the concept
    MDMA is built on — while looking like ordinary data."""
    s = BlackBoxSubject(complete=lambda p, n: reply, model_id="m")
    assert choose(s, "q", [" x", " y"], mode="generative", seed=0, item_id=0) == expected


def test_every_pairing_reference_resolves_in_the_registry():
    """Regression: pairing pointed at 'gpt-oss-20b' before it was registered, so the
    recommended ruler for every GPT reading raised KeyError on lookup."""
    from noetica_impair.models import registry
    for target, p in pairing.PAIRINGS.items():
        if p.reference_key is None:
            continue
        registry.get(p.reference_key)   # raises if absent


def test_the_ungated_reference_is_reachable_without_a_licence():
    """gpt-oss is Apache 2.0; Gemma and Llama are gated. That difference decides what
    can run before an HF licence has been accepted."""
    from noetica_impair.models import registry
    m = registry.get("gpt-oss-20b")
    assert m.arch == "moe" and m.moe.n_experts == 32 and m.moe.top_k == 4
    assert "UNGATED" in m.notes
