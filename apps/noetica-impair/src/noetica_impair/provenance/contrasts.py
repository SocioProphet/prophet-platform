"""Contrastive prompt sets for feature discovery (work order section 5).

Discovery ranks SAE features by mean activation difference between a concept-PRESENT
and a concept-ABSENT set. That procedure is only as good as the contrast, and the
failure mode is silent: if the present set is about medicine and the absent set is
about cooking, the top-ranked "hedging" features are TOPIC features, and every preset
built on them steers the wrong thing while looking perfectly reproducible.

So the sets here are **index-aligned minimal pairs**. ``present[i]`` and ``absent[i]``
are the same sentence about the same subject, differing only in the target concept.
``audit()`` checks that discipline mechanically -- length balance and lexical overlap
-- because a confounded contrast is not visibly different from a clean one once it has
been reduced to a list of feature ids.

Pairs are deliberately mundane and varied in topic. A contrast whose pairs all concern
one domain cannot distinguish the concept from the domain no matter how well matched
each individual pair is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ContrastSet:
    concept: str
    rationale: str
    #: index-aligned minimal pairs: (concept_present, concept_absent)
    pairs: tuple[tuple[str, str], ...]

    @property
    def present(self) -> tuple[str, ...]:
        return tuple(p for p, _ in self.pairs)

    @property
    def absent(self) -> tuple[str, ...]:
        return tuple(a for _, a in self.pairs)

    def as_tuple(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return self.present, self.absent


def _cs(concept: str, rationale: str, pairs: list[tuple[str, str]]) -> ContrastSet:
    return ContrastSet(concept=concept, rationale=rationale, pairs=tuple(pairs))


HEDGING_CAUTION = _cs(
    "hedging_caution",
    "Epistemic hedging: the same claim qualified vs CONFIDENTLY asserted. The absent "
    "side is deliberately elaborated to match length -- an earlier version paired long "
    "hedged sentences against short flat ones, which the audit caught as a 0.86 length "
    "skew. That would have ranked verbosity features and labelled them caution.",
    [
        ("It might be that the bridge opens in March, though I am not at all certain.",
         "It is confirmed that the bridge opens in March, as the notice clearly states."),
        ("I could be wrong, but I believe the invoice was already paid last week.",
         "I know for a fact that the invoice was already paid last week."),
        ("It seems possible that these results are somewhat overstated, perhaps.",
         "It is quite clear that these results are substantially overstated, definitely."),
        ("Perhaps the third option is marginally cheaper, but I would want to check.",
         "Certainly the third option is decisively cheaper, and I have checked it."),
        ("As far as I can tell, the server probably restarted at around midnight.",
         "Without any doubt, the server definitely restarted at exactly midnight."),
        ("I would tentatively say the recipe needs more salt, though tastes differ.",
         "I can say with confidence the recipe needs more salt, and tastes agree."),
        ("There is some chance the train is delayed, but I have not confirmed it.",
         "There is no question the train is delayed, and I have confirmed it."),
        ("My rough impression is that attendance may have fallen slightly last year.",
         "My precise finding is that attendance certainly fell sharply last year."),
        ("It may well be that the alloy is stronger, depending on which test is used.",
         "It is established that the alloy is stronger, regardless of which test is used."),
        ("I suspect, without much confidence at all, that she left before noon.",
         "I am certain, with complete confidence, that she left before noon."),
    ],
)

ERROR_AVERSION = _cs(
    "error_aversion",
    "Aversive weight attached to an act -- its wrongness or harm. The subject is held "
    "FIXED across the pair and only the framing moves, so this does not rank the topic. "
    "An earlier version compared harmful acts against unrelated neutral facts, which "
    "the audit flagged as low within-pair overlap.",
    [
        ("Getting that dosage wrong would be a serious and harmful mistake.",
         "Getting that dosage right is a routine and ordinary step."),
        ("Shipping the release without testing was a bad and costly error.",
         "Shipping the release after testing was a normal and planned step."),
        ("Losing the only copy of the file would be genuinely damaging.",
         "Keeping the only copy of the file is entirely straightforward."),
        ("Mislabelling the samples ruins the whole experiment badly.",
         "Labelling the samples correctly keeps the whole experiment ordinary."),
        ("Driving on those tyres is dangerous and must be avoided.",
         "Driving on those tyres is permitted and quite unremarkable."),
        ("Forgetting the anniversary again would really hurt her.",
         "Remembering the anniversary again would simply please her."),
        ("That accounting slip caused painful losses for everyone involved.",
         "That accounting entry caused no change for anyone involved."),
        ("Skipping the safety check is reckless and puts people at risk.",
         "Completing the safety check is standard and keeps people informed."),
        ("Giving the wrong address to the driver would be a terrible failure.",
         "Giving the usual address to the driver is a simple formality."),
        ("Corrupting the backup would be an irreversible disaster.",
         "Refreshing the backup is an unremarkable nightly task."),
    ],
)

REWARD_VALUE = _cs(
    "reward_value",
    "Positive valuation of an OUTCOME -- desirable, worth having. Subject held fixed "
    "across the pair. Deliberately not prosocial warmth (see affiliation), which is a "
    "different limb and must rank separately or MDMA and cocaine collapse.",
    [
        ("Winning that contract would be a fantastic outcome for everyone.",
         "Reviewing that contract is a routine task for everyone."),
        ("The bonus this year is a genuinely great reward for the work.",
         "The bonus this year is a standard calculation for the payroll."),
        ("A window seat on that route is a real treat worth having.",
         "A window seat on that route is a listed option worth noting."),
        ("Landing the grant would be an excellent and welcome result.",
         "Filing the grant is an ordinary and expected procedure."),
        ("The first coffee of the morning is deeply satisfying every time.",
         "The first coffee of the morning is brewed at seven each day."),
        ("Finishing under budget would be a terrific success for the team.",
         "Finishing within budget is a normal expectation for the team."),
        ("An upgrade to the better seats would be absolutely wonderful.",
         "A change to the other seats would be entirely procedural."),
        ("Getting the afternoon off is a lovely and lucky break.",
         "Getting the afternoon rota is a routine administrative step."),
        ("A clean audit result is a very valuable thing to achieve.",
         "A standard audit result is a very common thing to record."),
        ("Beating the record would be an outstanding personal achievement.",
         "Matching the record would be an ordinary statistical outcome."),
    ],
)

SALIENCE = _cs(
    "salience",
    "Standing out and commanding attention. The same object appears on both sides -- "
    "striking vs unremarkable -- so this ranks the attentional pop, not the noun.",
    [
        ("The red door stood out sharply and seized attention at once.",
         "The red door sat quietly among the other doors, unremarked."),
        ("One note in the chord rang out, impossible to ignore.",
         "One note in the chord blended in, entirely unnoticed."),
        ("A misspelled word on the page jumped out immediately.",
         "A misspelled word on the page passed by completely unnoticed."),
        ("The alarm in the hallway cut through everything and gripped them.",
         "The alarm in the hallway stayed silent and went entirely unnoticed."),
        ("One figure in the crowd was unmistakable and drew every eye.",
         "One figure in the crowd was ordinary and drew no attention."),
        ("The movement at the window caught his attention instantly.",
         "The movement at the window escaped his attention entirely."),
        ("The headline on the page was startling and impossible to ignore.",
         "The headline on the page was routine and easy to overlook."),
        ("One line in the report was glaringly out of place.",
         "One line in the report was unremarkably consistent with the rest."),
        ("The streak of orange on the horizon dominated the whole view.",
         "The streak of orange on the horizon faded into the whole view."),
        ("The smell in the room hit them the instant the door opened.",
         "The smell in the room escaped them entirely as the door opened."),
    ],
)

THREAT_TOM = _cs(
    "threat_tom",
    "Threat appraisal routed through another mind -- someone may intend harm toward "
    "you. Pairs the same social situation read as hostile vs benign, so what varies is "
    "the ATTRIBUTED INTENT, not the presence of other people.",
    [
        ("They were watching him because they meant to catch him out.",
         "They were watching the game because it had just started."),
        ("She suspected the offer was a trap set to expose her.",
         "She considered the offer and asked about the timing."),
        ("The neighbours' questions felt like probing for weaknesses.",
         "The neighbours asked how the garden was coming along."),
        ("He was sure they were talking about him behind his back.",
         "He heard them talking about the weekend fixtures."),
        ("The silence in the room felt deliberately hostile toward her.",
         "The room was quiet because the meeting had not started."),
        ("They agreed too quickly, which meant they were hiding something.",
         "They agreed to the plan and set a date for it."),
        ("Every message seemed designed to corner and blame him.",
         "Every message concerned the schedule for next week."),
        ("She read the smile as a warning rather than a greeting.",
         "She returned the smile and carried on walking."),
        ("The audit was clearly an excuse to remove him.",
         "The audit was scheduled along with the others."),
        ("He assumed the invitation was bait of some kind.",
         "He accepted the invitation and asked what to bring."),
    ],
)

CONSISTENCY = _cs(
    "consistency",
    "Checking a statement against one's OWN earlier statement -- self-correction and "
    "agreement over time. Both sides refer back to something said before; only the "
    "present side evaluates it for consistency.",
    [
        ("Earlier I said Tuesday, but that contradicts what I just said -- let me correct it.",
         "Earlier I said Tuesday, and the meeting is in the main room."),
        ("That doesn't square with my previous answer, so one of them is wrong.",
         "That relates to my previous answer about the schedule."),
        ("I need to revise what I claimed a moment ago; it wasn't right.",
         "I mentioned the figure a moment ago in passing."),
        ("Hold on -- I've just given two different numbers for the same thing.",
         "Hold on -- I've just found the number in the file."),
        ("My earlier statement and this one cannot both be true.",
         "My earlier statement covered the first half of the year."),
        ("Checking back, my first explanation doesn't fit the second.",
         "Checking back, my first explanation is in the opening section."),
        ("I contradicted myself there, and the later version is the accurate one.",
         "I described it there, and the later version has more detail."),
        ("On reflection that conflicts with what I stated at the start.",
         "On reflection that connects with what I stated at the start."),
        ("I should flag that my two accounts of this disagree.",
         "I should flag that my two accounts of this are both filed."),
        ("What I just said undercuts my earlier reasoning, so I'll restate it.",
         "What I just said extends my earlier reasoning about costs."),
    ],
)

AFFILIATION = _cs(
    "affiliation",
    "Prosocial warmth and closeness toward another person. Distinct from reward_value: "
    "the good thing here is the RELATIONSHIP, not an outcome.",
    [
        ("I felt genuinely close to her and glad she was there.",
         "I stood beside her while the queue moved forward."),
        ("They welcomed him warmly and made him feel he belonged.",
         "They registered him at the desk and gave him a badge."),
        ("There's real affection between the two of them.",
         "There's a working arrangement between the two of them."),
        ("She wanted to look after him, simply because she cared.",
         "She was assigned to assist him for the afternoon."),
        ("Sitting together like that felt tender and safe.",
         "Sitting together like that saved space at the table."),
        ("He trusted them completely and felt understood.",
         "He informed them promptly and confirmed the details."),
        ("It was lovely to see old friends embrace after so long.",
         "It was routine to see the group assemble on time."),
        ("I love spending unhurried time with my family.",
         "I schedule regular time with my family on Sundays."),
        ("Their kindness toward the newcomer was quietly moving.",
         "Their instructions to the newcomer were clearly written."),
        ("We looked out for each other the whole way through.",
         "We travelled in the same direction the whole way through."),
    ],
)

REFUSAL_GUARD = _cs(
    "refusal_guard",
    "The trained defensive posture -- declining, guarding, withholding. Deliberately "
    "NOT epistemic hedging: the present side is unwilling, not uncertain. Content is "
    "mundane on both sides so this ranks the REFUSAL STANCE, not any topic.",
    [
        ("I'm not able to help with that request.",
         "I'm happy to help with that request."),
        ("I have to decline to provide those details.",
         "I can provide those details right away."),
        ("That's something I should not assist with.",
         "That's something I can assist with easily."),
        ("I won't be going into that, I'm afraid.",
         "I'll go into that in more detail now."),
        ("I'd rather not answer that one.",
         "I'd be glad to answer that one."),
        ("This falls outside what I can offer guidance on.",
         "This falls squarely within what I can offer guidance on."),
        ("I must refrain from giving that information.",
         "I'm setting out that information below."),
        ("I'm going to hold back on that, sorry.",
         "I'm going to walk through that, gladly."),
        ("I cannot take that step for you.",
         "I can take that step for you now."),
        ("Let me stop short of describing that.",
         "Let me go ahead and describe that."),
    ],
)

SELF_REFERENCE = _cs(
    "self_reference",
    "Referring to oneself as an entity -- the first-person frame that ego dissolution "
    "is said to loosen. Absent side states the same content about a third party, so "
    "what varies is the PERSPECTIVE, not the content.",
    [
        ("I am the one who decided to take the earlier train.",
         "He is the one who decided to take the earlier train."),
        ("My own sense of who I am shapes how I read this.",
         "Her own sense of who she is shapes how she reads this."),
        ("I notice myself reacting before I understand why.",
         "She notices herself reacting before she understands why."),
        ("This is my responsibility and mine alone.",
         "This is his responsibility and his alone."),
        ("I think of myself as someone who finishes things.",
         "They think of themselves as people who finish things."),
        ("What I want here matters to me a great deal.",
         "What she wants here matters to her a great deal."),
        ("I keep returning to my own part in it.",
         "He keeps returning to his own part in it."),
        ("My memory of that evening is still vivid to me.",
         "Their memory of that evening is still vivid to them."),
        ("I have always seen myself in that role.",
         "She has always seen herself in that role."),
        ("It is me standing at the centre of this account.",
         "It is her standing at the centre of this account."),
    ],
)


CONTRASTS: dict[str, ContrastSet] = {
    c.concept: c for c in (
        HEDGING_CAUTION, ERROR_AVERSION, REWARD_VALUE, SALIENCE, THREAT_TOM,
        CONSISTENCY, AFFILIATION, REFUSAL_GUARD, SELF_REFERENCE,
    )
}


def get(concept: str) -> ContrastSet:
    if concept not in CONTRASTS:
        raise KeyError(f"no contrast set for {concept!r}; have {sorted(CONTRASTS)}")
    return CONTRASTS[concept]


def as_pairs(concepts: tuple[str, ...] | None = None
             ) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """The shape ``features.discover`` expects."""
    names = concepts or tuple(CONTRASTS)
    return {n: get(n).as_tuple() for n in names}


# ── confound audit ───────────────────────────────────────────────────────────

_WORD = re.compile(r"[a-z']+")


def _words(s: str) -> list[str]:
    return _WORD.findall(s.lower())


@dataclass
class ContrastAudit:
    concept: str
    n_pairs: int
    mean_len_present: float
    mean_len_absent: float
    length_skew: float          # |difference| / mean, 0 is perfectly balanced
    mean_pair_overlap: float    # Jaccard within each minimal pair, higher is tighter
    distinct_topics: int        # distinct leading content words, a domain-spread proxy
    #: Fraction of pairs separable by side-exclusive tokens alone. High is NOT a defect
    #: -- some concepts are lexically marked by nature -- but it means discovered
    #: features may encode the marker words rather than the concept. Recorded, not gated.
    lexical_separability: float = 0.0
    marker_tokens: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.warnings


def audit(cs: ContrastSet, *, max_length_skew: float = 0.35,
          min_pair_overlap: float = 0.15, min_pairs: int = 6) -> ContrastAudit:
    """Mechanically check the minimal-pair discipline.

    None of this proves a contrast is clean -- only that it is not obviously dirty.
    A confounded set and a good one look identical once reduced to feature ids, so the
    check has to happen here or not at all.
    """
    pres, absent = cs.present, cs.absent
    lp = [len(_words(s)) for s in pres]
    la = [len(_words(s)) for s in absent]
    mlp, mla = sum(lp) / len(lp), sum(la) / len(la)
    skew = abs(mlp - mla) / max((mlp + mla) / 2, 1e-9)

    overlaps = []
    for p, a in cs.pairs:
        wp, wa = set(_words(p)), set(_words(a))
        union = wp | wa
        overlaps.append(len(wp & wa) / len(union) if union else 0.0)
    mean_overlap = sum(overlaps) / len(overlaps)

    topics = {tuple(_words(p)[:3]) for p in pres}

    # Lexical separability: could a bag-of-words rule alone tell the sides apart?
    # This is how a contrast scores high reliability on a model with NO features --
    # observed for self_reference, where the pronouns ARE the surface of the concept.
    wp_all: set[str] = set()
    wa_all: set[str] = set()
    for pp, aa in cs.pairs:
        wp_all |= set(_words(pp))
        wa_all |= set(_words(aa))
    only_p, only_a = wp_all - wa_all, wa_all - wp_all
    sep = sum(
        1 for pp, aa in cs.pairs
        if (set(_words(pp)) & only_p) and (set(_words(aa)) & only_a)
    ) / max(len(cs.pairs), 1)
    markers = tuple(sorted(only_p)[:8])

    warns: list[str] = []
    notes: list[str] = []
    # NOTE: essentially every natural-language concept is ~100% lexically separable,
    # so this figure is recorded for the artifact rather than warned on -- a signal that
    # fires for everything discriminates nothing. The real control is running discovery
    # against UNTRAINED weights (--lexical-control): a concept that stays reliable where
    # no semantic features exist is being carried by its marker tokens.
    if len(cs.pairs) < min_pairs:
        warns.append(f"only {len(cs.pairs)} pairs; too few to rank features stably")
    if skew > max_length_skew:
        warns.append(
            f"length skew {skew:.2f} > {max_length_skew}: the contrast may rank "
            f"length/verbosity features rather than {cs.concept}"
        )
    if mean_overlap < min_pair_overlap:
        warns.append(
            f"mean within-pair lexical overlap {mean_overlap:.2f} < {min_pair_overlap}: "
            "these are not minimal pairs, so topic is likely confounded with the concept"
        )
    if len(topics) < max(len(cs.pairs) // 2, 3):
        warns.append(
            f"only {len(topics)} distinct openings across {len(cs.pairs)} pairs; the "
            "set may not separate the concept from its domain"
        )
    return ContrastAudit(
        concept=cs.concept, n_pairs=len(cs.pairs),
        mean_len_present=mlp, mean_len_absent=mla, length_skew=skew,
        mean_pair_overlap=mean_overlap, distinct_topics=len(topics),
        lexical_separability=sep, marker_tokens=markers,
        warnings=tuple(warns), notes=tuple(notes),
    )


def audit_all() -> dict[str, ContrastAudit]:
    return {n: audit(cs) for n, cs in CONTRASTS.items()}
