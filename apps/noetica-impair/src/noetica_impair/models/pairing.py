"""Which white-box model is the right ruler for a given black-box model.

A black box cannot be hooked, so it cannot be dosed. What it CAN do is run the same
probe battery, yielding a FacultyVector. To express that in mechanical units it has to
be located on a dose ladder measured on some white-box model -- and the choice of that
model is a scientific decision, not a convenience.

**Use the lab's own open-weights model where one exists.** gpt-oss to judge GPT, Gemma
to judge Gemini. Same lab means shared post-training philosophy, shared refusal and
safety training, related tokenizer lineage and house style -- so a difference in the
faculty profile is more plausibly about the condition under test than about two
unrelated training pipelines.

**But same-lab is a PROXY, never identity.** gpt-oss-20b is not GPT-5: different scale,
different architecture, different data. It reduces confounds; it does not eliminate
them. So every pairing carries an explicit ``kinship`` grade, and every equivalence
statement built on it records which ruler was used and how closely related that ruler
actually is. "Reads as ALCOHOL@0.4" is meaningless without "as measured against
gpt-oss-20b's ladder".

**Anthropic has no open-weight model.** Their open releases are interpretability
tooling, not Claude weights. Claude can still be measured -- but only against another
lab's ruler, which is a materially weaker claim. The registry says so rather than
quietly substituting a convenient reference.
"""

from __future__ import annotations

from dataclasses import dataclass

#: How closely the white-box ruler is related to the black-box target. Ordered from
#: strongest to weakest; equivalence claims inherit this grade.
KINSHIP = ("same_lab_open_weights", "same_family_open", "unrelated", "none_available")

KINSHIP_NOTE = {
    "same_lab_open_weights":
        "the lab's own open-weights model: shared post-training philosophy, refusal "
        "training and tokenizer lineage. The best ruler available, still a proxy.",
    "same_family_open":
        "an open model from the same architecture family but not the same lab's own "
        "release. Weaker: training recipe and safety tuning may differ substantially.",
    "unrelated":
        "a generic ruler from a different lab. The equivalence is a rough calibration "
        "only, and differences may reflect the two training pipelines rather than the "
        "condition under test.",
    "none_available":
        "no open-weights model from this lab exists. Any equivalence is calibrated on "
        "another lab's ruler and must be reported as such.",
}


@dataclass(frozen=True)
class ReferencePairing:
    """A black-box target and the white-box model used to measure it."""

    target: str                 # black-box model / family being judged
    vendor: str
    reference_key: str | None   # registry key of the white-box ruler
    reference_hf_id: str | None
    kinship: str
    rationale: str
    has_sae: bool = False       # can the mechanical ladder include feature steering?

    def __post_init__(self) -> None:
        if self.kinship not in KINSHIP:
            raise ValueError(f"unknown kinship {self.kinship!r}")

    @property
    def note(self) -> str:
        return KINSHIP_NOTE[self.kinship]

    @property
    def weakly_calibrated(self) -> bool:
        return self.kinship in ("unrelated", "none_available")


PAIRINGS: dict[str, ReferencePairing] = {}


def _add(p: ReferencePairing) -> ReferencePairing:
    PAIRINGS[p.target] = p
    return p


_add(ReferencePairing(
    target="gpt", vendor="OpenAI",
    reference_key="gpt-oss-20b", reference_hf_id="openai/gpt-oss-20b",
    kinship="same_lab_open_weights",
    rationale=(
        "OpenAI released gpt-oss-120b and gpt-oss-20b under Apache 2.0, trained with "
        "techniques informed by their frontier systems. Same lab, so refusal training "
        "and post-training recipe are related to the API models. Not the same model: "
        "gpt-oss-20b is 21B with 3.6B active and is NOT a stand-in for a frontier GPT."
    ),
))

_add(ReferencePairing(
    target="gemini", vendor="Google",
    reference_key="gemma2-9b", reference_hf_id="google/gemma-2-9b-it",
    kinship="same_lab_open_weights",
    rationale=(
        "Gemma is Google's open-weights line alongside the Gemini API models, and is "
        "the strongest pairing for THIS rig specifically: Gemma Scope SAEs exist, so "
        "the reference ladder can include feature steering rather than mechanical ops "
        "alone. Every SAE-dependent limb is measurable on this ruler."
    ),
    has_sae=True,
))

_add(ReferencePairing(
    target="mistral-api", vendor="Mistral",
    reference_key="mixtral-8x7b", reference_hf_id="mistralai/Mixtral-8x7B-v0.1",
    kinship="same_lab_open_weights",
    rationale="Mistral ships open weights alongside its API; Mixtral additionally gives "
              "a legible MoE router for the routing-KL readout.",
))

_add(ReferencePairing(
    target="deepseek-api", vendor="DeepSeek",
    reference_key="deepseek-r1-distill",
    reference_hf_id="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    kinship="same_lab_open_weights",
    rationale="DeepSeek publishes open weights alongside its API. Note the distill is a "
              "Llama-architecture student, so its shared-expert layout differs from full "
              "V3 -- the MoE split rule does not transfer unchanged.",
))

_add(ReferencePairing(
    target="claude", vendor="Anthropic",
    reference_key=None, reference_hf_id=None,
    kinship="none_available",
    rationale=(
        "Anthropic has NOT released open-weight Claude models; their open releases are "
        "interpretability tooling, not weights. There is therefore no same-lab ruler. "
        "Claude can be run through the identical battery and compared on retained "
        "fraction, but any MECHANICAL equivalence must borrow another lab's ladder and "
        "be reported as weakly calibrated. Do not silently substitute a convenient "
        "reference and present the result as if it were same-lab."
    ),
))


def get(target: str) -> ReferencePairing:
    key = target.lower()
    if key in PAIRINGS:
        return PAIRINGS[key]
    for name, p in PAIRINGS.items():          # prefix match: "gpt-5" -> "gpt"
        if key.startswith(name):
            return p
    return ReferencePairing(
        target=target, vendor="unknown", reference_key=None, reference_hf_id=None,
        kinship="unrelated",
        rationale=f"no registered pairing for {target!r}; any ruler is a generic one.",
    )


def reference_for(target: str) -> str | None:
    return get(target).reference_key


def describe(target: str) -> dict:
    p = get(target)
    return {
        "target": p.target, "vendor": p.vendor,
        "reference_key": p.reference_key, "reference_hf_id": p.reference_hf_id,
        "kinship": p.kinship, "kinship_note": p.note,
        "weakly_calibrated": p.weakly_calibrated,
        "reference_has_sae": p.has_sae,
        "rationale": p.rationale,
    }
