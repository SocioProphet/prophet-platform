"""PII redaction over transcript text — the governance-critical stage of the substrate.

This module is pure Python with no third-party dependency, which is deliberate: everything
else in this service degrades to "adapter unavailable" in an environment without ASR
tooling, but redaction must work everywhere, always, or the guarantee it provides is
conditional on an install. It is the one stage here that is genuinely production-grade.

Two properties are non-negotiable:

  1. NOTHING IS ECHOED. A `RedactionFinding` records the class, the detector that fired,
     and the span — never the removed value. The estate rule is that scanners do not echo
     their matches; a manifest that quoted the credit-card number it found would simply
     relocate the leak into the audit trail.

  2. IT RUNS BEFORE EMISSION. The pipeline is structured so raw `TranscriptSegment`s are
     consumed by the redactor and only `RedactedSegment`s can be constructed downstream
     (see types.py). The audit log records the redact stage with its ordinal so the
     ordering is checkable after the fact, not merely asserted.

ASR-SPECIFIC DETECTION
---------------------
Redactors written for typed text miss most PII in a transcript, because ASR does not emit
"413-555-0134" — it emits "four one three five five five oh one three four". The
`spoken_number_sequence` detector below handles digit-word runs (including "double seven"
/ "triple eight" and mixed "413 five five five" output), which is the single most commonly
missed class when a text redactor is pointed at voice. Spoken email forms ("jane dot doe
at example dot com") are handled for the same reason.

FALSE POSITIVES
---------------
Structural checks run where the format supports one: Luhn for card-shaped digit runs,
ISO 7064 mod-97 for IBANs, issuing-range rules for US SSNs. Those are what keep a
16-digit order reference from being redacted as a card. Where no check exists (street
addresses, phones) the detector is tuned toward over-redaction: in a governance substrate
a false positive costs a redacted street name, a false negative costs a disclosure.

See `POLICY` at the bottom for the classes covered and — as importantly — the ones not.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Iterator, Sequence

from .types import RedactedSegment, RedactionFinding, RedactionResult, TranscriptSegment

POLICY_VERSION = "voice-substrate-redaction/1.0.0"
PLACEHOLDER = "[REDACTED:{type}]"

# ---------------------------------------------------------------------------------------
# Structural validators — these are what separate a real redactor from a regex pile.
# ---------------------------------------------------------------------------------------


def luhn_ok(digits: str) -> bool:
    """Luhn (ISO/IEC 7812-1) mod-10 checksum.

    Applied to every card-shaped digit run before it is redacted as a card. Roughly 90% of
    random 16-digit strings fail Luhn, so this is the difference between "redacts card
    numbers" and "redacts every long number in the transcript".
    """
    if not digits.isdigit() or not 12 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = ord(ch) - 48
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def iban_ok(candidate: str) -> bool:
    """ISO 13616 IBAN check: rearrange, letters -> digits, mod 97 == 1."""
    s = re.sub(r"[\s\-]", "", candidate).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    rearranged = s[4:] + s[:4]
    total = 0
    for ch in rearranged:
        if ch.isdigit():
            total = (total * 10 + (ord(ch) - 48)) % 97
        else:
            total = (total * 100 + (ord(ch) - 55)) % 97
    return total == 1


def _digit_count(s: str) -> int:
    return sum(1 for c in s if c.isdigit())


# ---------------------------------------------------------------------------------------
# Detector plumbing
# ---------------------------------------------------------------------------------------

Span = tuple[int, int]


@dataclass(frozen=True)
class Detector:
    """A named PII finder. `find` yields (start, end) spans in the supplied text.

    `priority` resolves overlaps: lower wins. An email containing digits must beat the
    phone detector on the same span, a Luhn-valid card must beat a generic digit run, and
    so on. Overlap resolution is greedy by (priority, start, -length).
    """

    name: str
    type: str
    priority: int
    find: Callable[[str], Iterator[Span]]


def _regex_detector(
    name: str,
    type_: str,
    priority: int,
    pattern: str,
    *,
    flags: int = 0,
    group: int = 0,
    accept: Callable[[str], bool] | None = None,
    backtrack: bool = False,
) -> Detector:
    rx = re.compile(pattern, flags)

    def find(text: str) -> Iterator[Span]:
        for m in rx.finditer(text):
            if m.group(group) is None:
                continue
            value = m.group(group)
            start, end = m.span(group)
            if accept is not None and not accept(value):
                if not backtrack:
                    continue
                # A greedy pattern can over-reach into following words, so a structurally
                # validated class (IBAN) would be dropped entirely rather than shortened.
                # Retry shorter suffixes; the checksum decides where the value really ends.
                hit = None
                for e in range(end - 1, start + 4, -1):
                    if accept(text[start:e]):
                        hit = e
                        break
                if hit is None:
                    continue
                end = hit
            # trim trailing whitespace/punctuation that a greedy group may have taken
            while end > start and text[end - 1] in " \t.,;:":
                end -= 1
            if end > start:
                yield start, end

    return Detector(name=name, type=type_, priority=priority, find=find)


# ---------------------------------------------------------------------------------------
# Written-form detectors
# ---------------------------------------------------------------------------------------

_MONTHS = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)

_US_STATES = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|"
    "NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
)

_STREET_SUFFIX = (
    r"street|st|road|rd|avenue|ave|lane|ln|drive|dr|boulevard|blvd|way|close|court|ct|"
    r"place|pl|terrace|terr|crescent|square|sq|highway|hwy|parkway|pkwy|circle|cir|"
    r"trail|trl|gardens|gdns|mews|row"
)

_DOB_CUE = re.compile(
    r"\b(?:born(?:\s+on)?|date\s+of\s+birth|d\.?\s?o\.?\s?b\.?|birth\s*date|birthday)\b",
    re.IGNORECASE,
)
_DOB_CUE_WINDOW = 80  # characters before the date in which a cue makes it a DOB

_DATE_PATTERNS = (
    r"(?<!\d)\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}(?!\d)",
    r"(?<!\d)\d{4}[/\-]\d{1,2}[/\-]\d{1,2}(?!\d)",
    rf"\b(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b",
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTHS})\s+\d{{4}}\b",
)


def _date_spans(text: str) -> list[Span]:
    spans: list[Span] = []
    for pat in _DATE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            spans.append(m.span())
    return sorted(set(spans))


def _dob_detector_find(text: str) -> Iterator[Span]:
    """A date is treated as a date of birth only when a birth cue precedes it closely.

    This is a real limitation, stated plainly rather than papered over: a date alone
    carries no marker distinguishing a birth date from a meeting date, so cue-gating is
    the honest default. `redact_all_dates=True` on the policy widens this to every date
    at the cost of heavy over-redaction.
    """
    cues = [m.end() for m in _DOB_CUE.finditer(text)]
    if not cues:
        return
    for start, end in _date_spans(text):
        if any(0 <= start - c <= _DOB_CUE_WINDOW for c in cues):
            yield start, end


def _all_dates_find(text: str) -> Iterator[Span]:
    yield from _date_spans(text)


def _accept_phone(value: str) -> bool:
    return 7 <= _digit_count(value) <= 15


def _accept_card(value: str) -> bool:
    return luhn_ok(re.sub(r"[^\d]", "", value))


def _accept_national_id_value(value: str) -> bool:
    return _digit_count(value) >= 4


BUILTIN_DETECTORS: tuple[Detector, ...] = (
    # --- email (highest priority: emails contain digits and dots that other detectors want)
    _regex_detector(
        "email_written", "EMAIL", 10,
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    ),
    _regex_detector(
        "email_spoken", "EMAIL", 11,
        r"\b[A-Za-z0-9._\-]+(?:\s+(?:dot|underscore|dash|hyphen)\s+[A-Za-z0-9._\-]+)*"
        r"\s+at\s+[A-Za-z0-9\-]+(?:\s+dot\s+[A-Za-z0-9\-]+)+\b",
        flags=re.IGNORECASE,
    ),
    # --- bank / card (structurally validated, so they outrank generic digit runs)
    _regex_detector(
        "iban_mod97", "IBAN", 20,
        r"\b[A-Za-z]{2}\d{2}(?:[ \-]?[A-Za-z0-9]){10,30}\b",
        accept=iban_ok,
        backtrack=True,
    ),
    _regex_detector(
        "credit_card_luhn", "CREDIT_CARD", 25,
        r"(?<![\d\-])(?:\d[ \-]?){12,18}\d(?!\d)",
        accept=_accept_card,
    ),
    # --- national identifiers
    _regex_detector(
        # US SSN with issuing-range exclusions (area 000/666/900-999, group 00, serial 0000
        # are never issued) — these cut a large slice of the false positives a bare
        # \d{3}-\d{2}-\d{4} would produce.
        "us_ssn", "NATIONAL_ID", 30,
        r"\b(?!000|666|9\d\d)\d{3}[ \-](?!00)\d{2}[ \-](?!0000)\d{4}\b",
    ),
    _regex_detector(
        "uk_nino", "NATIONAL_ID", 31,
        r"\b[ABCEGHJKLMNOPRSTWXYZ][ABCEGHJKLMNPRSTWXYZ]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b",
        flags=re.IGNORECASE,
    ),
    _regex_detector(
        # Context-gated: an identifier introduced by name ("my passport number is ...").
        # Only the value is redacted, not the cue — the audit reader should still be able
        # to see that a passport number was disclosed.
        "national_id_context", "NATIONAL_ID", 32,
        r"\b(?:social\s+security(?:\s+number)?|ssn|national\s+insurance(?:\s+number)?|nino|"
        r"passport(?:\s+number)?|driver'?s?\s+licen[cs]e(?:\s+number)?|tax\s+file\s+number|"
        r"tfn|medicare\s+(?:number|card)|nhs\s+number|aadhaar(?:\s+number)?|"
        r"national\s+id(?:\s+number)?)"
        r"(?:\s+(?:is|number|no\.?|#))?[\s:#]*"
        r"([A-Za-z0-9][A-Za-z0-9\-]*(?:[ \-][A-Za-z0-9]+){0,5})",
        flags=re.IGNORECASE,
        group=1,
        accept=_accept_national_id_value,
    ),
    # --- telephone (several international shapes; all post-filtered on digit count)
    _regex_detector(
        "phone_international_e164", "PHONE", 40,
        r"(?<![\w+])\+\d{1,3}[\s.\-]?(?:\(?\d{1,4}\)?[\s.\-]?){1,5}\d{2,4}(?!\d)",
        accept=_accept_phone,
    ),
    _regex_detector(
        "phone_nanp_separated", "PHONE", 41,
        r"(?<![\d\-])\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}(?!\d)",
        accept=_accept_phone,
    ),
    _regex_detector(
        "phone_nanp_compact", "PHONE", 42,
        r"(?<!\d)[2-9]\d{2}[2-9]\d{6}(?!\d)",
        accept=_accept_phone,
    ),
    _regex_detector(
        # UK/EU national trunk form: leading 0, 10-11 digits total.
        "phone_uk_trunk", "PHONE", 43,
        r"(?<![\d\-])0\d{1,4}[\s.\-]?\d{3,4}[\s.\-]?\d{3,5}(?!\d)",
        accept=lambda v: 10 <= _digit_count(v) <= 11,
    ),
    _regex_detector(
        "phone_context", "PHONE", 44,
        r"\b(?:phone|mobile|cell(?:phone)?|telephone|tel|fax|call\s+me\s+(?:on|at)|"
        r"reach\s+me\s+(?:on|at)|number\s+is)\b[\s:#]*"
        r"((?:\+?\d[\d\s.\-()]{5,18}\d))",
        flags=re.IGNORECASE,
        group=1,
        accept=_accept_phone,
    ),
    # --- dates of birth (cue-gated; see _dob_detector_find)
    Detector("dob_cue_gated", "DATE_OF_BIRTH", 50, _dob_detector_find),
    # --- postal / street address
    _regex_detector(
        "street_address", "STREET_ADDRESS", 60,
        rf"\b\d{{1,5}}[A-Za-z]?\s+(?:[A-Za-z0-9'.\-]+\s+){{0,3}}(?:{_STREET_SUFFIX})\b\.?",
        flags=re.IGNORECASE,
    ),
    _regex_detector(
        "po_box", "STREET_ADDRESS", 61,
        r"\bp\.?\s?o\.?\s+box\s+\d{1,6}\b",
        flags=re.IGNORECASE,
    ),
    _regex_detector(
        "uk_postcode", "STREET_ADDRESS", 62,
        r"\b[A-Za-z]{1,2}\d[A-Za-z\d]?\s?\d[A-Za-z]{2}\b",
    ),
    _regex_detector(
        "us_zip_with_state", "STREET_ADDRESS", 63,
        rf"\b(?:{_US_STATES})\s+\d{{5}}(?:-\d{{4}})?\b",
    ),
)


# ---------------------------------------------------------------------------------------
# Spoken-digit runs — the ASR-specific class most text redactors miss entirely
# ---------------------------------------------------------------------------------------

_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "nought": "0", "naught": "0", "o": "0",
    "one": "1", "won": "1",
    "two": "2", "to": None, "too": None,          # None = ambiguous, never starts a run
    "three": "3", "tree": "3",
    "four": "4", "for": None, "fore": None,
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8", "ate": None,
    "nine": "9",
}
# Words that repeat the NEXT digit word ("double seven" -> 77).
_REPEATERS = {"double": 2, "triple": 3, "treble": 3}
# Filler permitted between digits without breaking the run.
_RUN_FILLER = {"dash", "hyphen", "space"}
_TOKEN_RX = re.compile(r"[A-Za-z]+|\d+")
_GAP_RX = re.compile(r"^[\s,\-–—.()]*$")

MIN_SPOKEN_DIGITS = 7  # shortest plausible phone/account number


def _resolve_digit_word(word: str) -> str | None:
    """Return the digit for an unambiguous digit word, else None.

    "to"/"too"/"for"/"fore"/"ate" are homophones ASR emits constantly in ordinary speech;
    they are accepted only as continuations of a run that is already established by
    unambiguous digit words, never as the token that starts one. Without that rule,
    "I have to go for a walk" becomes a redaction candidate.
    """
    return _DIGIT_WORDS.get(word.lower())


def _is_digit_word(word: str) -> bool:
    return word.lower() in _DIGIT_WORDS


def spoken_number_runs(
    text: str, min_digits: int = MIN_SPOKEN_DIGITS
) -> list[tuple[int, int, int, bool]]:
    """Find runs of spoken digits. Returns (start, end, digit_count, luhn_valid).

    Accepts mixed output — ASR frequently emits "413 five five five oh one three four"
    for a single dictated number — and expands "double"/"triple" repeaters. A run must
    contain at least one genuine digit *word*: pure numeric runs are the written-form
    detectors' job, and requiring a spoken token here stops adjacent unrelated figures
    ("in 2026 we shipped 1500 units") being glued into a false positive.
    """
    tokens = [(m.start(), m.end(), m.group()) for m in _TOKEN_RX.finditer(text)]
    runs: list[tuple[int, int, int, bool]] = []
    i = 0
    n = len(tokens)
    while i < n:
        start_idx = i
        digits: list[str] = []
        spoken_words = 0
        pending_repeat = 1
        last_end = None
        j = i
        established = False
        while j < n:
            tstart, tend, word = tokens[j]
            if last_end is not None:
                gap = text[last_end:tstart]
                if not _GAP_RX.match(gap) or len(gap) > 3:
                    break
            lower = word.lower()
            if word.isdigit():
                digits.extend(word * pending_repeat)
                pending_repeat = 1
                established = True
            elif lower in _REPEATERS:
                pending_repeat = _REPEATERS[lower]
            elif lower in _RUN_FILLER:
                pass
            elif _is_digit_word(lower):
                d = _resolve_digit_word(lower)
                if d is None:
                    # ambiguous homophone: only allowed inside an established run
                    if not established:
                        break
                    d = {"to": "2", "too": "2", "for": "4", "fore": "4", "ate": "8"}[lower]
                digits.extend(d * pending_repeat)
                pending_repeat = 1
                spoken_words += 1
                established = True
            else:
                break
            last_end = tend
            j += 1
        if j > start_idx and len(digits) >= min_digits and spoken_words >= 1:
            span_start = tokens[start_idx][0]
            span_end = tokens[j - 1][1]
            joined = "".join(digits)
            runs.append((span_start, span_end, len(joined), luhn_ok(joined)))
            i = j
        else:
            i = start_idx + 1
    return runs


def _spoken_sequence_find(text: str) -> Iterator[Span]:
    for start, end, _count, luhn in spoken_number_runs(text):
        if not luhn:
            yield start, end


def _spoken_card_find(text: str) -> Iterator[Span]:
    for start, end, count, luhn in spoken_number_runs(text):
        if luhn and 13 <= count <= 19:
            yield start, end


SPOKEN_DETECTORS: tuple[Detector, ...] = (
    Detector("spoken_card_luhn", "SPOKEN_CARD_NUMBER", 26, _spoken_card_find),
    Detector("spoken_number_sequence", "SPOKEN_NUMBER_SEQUENCE", 70, _spoken_sequence_find),
)


# ---------------------------------------------------------------------------------------
# Optional: spaCy NER person names. Real, and it does run in this environment — but it is
# opt-in and separately reported, because unlike everything above it depends on an install.
# ---------------------------------------------------------------------------------------

_SPACY_MODEL = "en_core_web_sm"
_spacy_nlp = None


def person_ner_available() -> tuple[bool, str]:
    if importlib.util.find_spec("spacy") is None:
        return False, "spacy not installed (pip install spacy && python -m spacy download en_core_web_sm)"
    try:
        import spacy  # noqa: PLC0415

        if not spacy.util.is_package(_SPACY_MODEL):
            return False, f"spaCy installed but model {_SPACY_MODEL} missing (python -m spacy download {_SPACY_MODEL})"
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"spacy import failed: {exc}"
    return True, f"spaCy {_SPACY_MODEL}"


def _person_find(text: str) -> Iterator[Span]:
    global _spacy_nlp
    if _spacy_nlp is None:
        import spacy  # noqa: PLC0415

        _spacy_nlp = spacy.load(_SPACY_MODEL, disable=["parser", "lemmatizer"])
    for ent in _spacy_nlp(text).ents:
        if ent.label_ == "PERSON":
            yield ent.start_char, ent.end_char


PERSON_NAME_DETECTOR = Detector("spacy_ner_person", "PERSON_NAME", 55, _person_find)


# ---------------------------------------------------------------------------------------
# Policy + redactor
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RedactionPolicy:
    min_spoken_digits: int = MIN_SPOKEN_DIGITS
    redact_all_dates: bool = False
    enable_person_names: bool = False


DEFAULT_POLICY = RedactionPolicy()


class Redactor:
    """Applies the detector set to text and returns redacted text + a value-free manifest."""

    def __init__(self, policy: RedactionPolicy = DEFAULT_POLICY) -> None:
        self.policy = policy
        detectors: list[Detector] = list(BUILTIN_DETECTORS)
        if policy.min_spoken_digits == MIN_SPOKEN_DIGITS:
            detectors.extend(SPOKEN_DETECTORS)
        else:
            md = policy.min_spoken_digits
            detectors.append(Detector(
                "spoken_card_luhn", "SPOKEN_CARD_NUMBER", 26,
                lambda t: (
                    (s, e) for s, e, c, l in spoken_number_runs(t, md) if l and 13 <= c <= 19
                ),
            ))
            detectors.append(Detector(
                "spoken_number_sequence", "SPOKEN_NUMBER_SEQUENCE", 70,
                lambda t: ((s, e) for s, e, _c, l in spoken_number_runs(t, md) if not l),
            ))
        if policy.redact_all_dates:
            detectors.append(Detector("any_date", "DATE", 51, _all_dates_find))
        if policy.enable_person_names:
            ok, _reason = person_ner_available()
            if ok:
                detectors.append(PERSON_NAME_DETECTOR)
        self.detectors: tuple[Detector, ...] = tuple(detectors)

    # -- introspection used by /policy and /healthz -------------------------------------
    @property
    def active_types(self) -> list[str]:
        return sorted({d.type for d in self.detectors})

    @property
    def active_detectors(self) -> list[dict[str, object]]:
        return [{"name": d.name, "type": d.type, "priority": d.priority} for d in self.detectors]

    # -- core ---------------------------------------------------------------------------
    def scan(self, text: str) -> list[RedactionFinding]:
        """Find PII spans without modifying anything. Overlaps resolved by priority."""
        candidates: list[tuple[int, int, int, str, str]] = []
        for det in self.detectors:
            for start, end in det.find(text):
                if end > start:
                    candidates.append((det.priority, start, end, det.type, det.name))
        candidates.sort(key=lambda c: (c[0], c[1], -(c[2] - c[1])))
        accepted: list[tuple[int, int, str, str]] = []
        for _prio, start, end, type_, name in candidates:
            if any(start < a_end and end > a_start for a_start, a_end, _t, _n in accepted):
                continue
            accepted.append((start, end, type_, name))
        accepted.sort(key=lambda a: a[0])
        return [
            RedactionFinding(type=t, detector=n, start=s, end=e, length=e - s)
            for s, e, t, n in accepted
        ]

    def redact(self, text: str) -> RedactionResult:
        findings = self.scan(text)
        out: list[str] = []
        cursor = 0
        for f in findings:
            out.append(text[cursor:f.start])
            out.append(PLACEHOLDER.format(type=f.type))
            cursor = f.end
        out.append(text[cursor:])
        redacted = "".join(out)
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.type] = counts.get(f.type, 0) + 1
        return RedactionResult(
            text=redacted,
            findings=tuple(findings),
            counts=counts,
            redacted_sha256=hashlib.sha256(redacted.encode("utf-8")).hexdigest(),
            policy_version=POLICY_VERSION,
        )

    def redact_segments(
        self, segments: Sequence[TranscriptSegment]
    ) -> tuple[list[RedactedSegment], RedactionResult]:
        """Redact per segment. Spans in each finding are offsets WITHIN that segment's text,
        and `segment_index` says which one — so an auditor can locate a removal without the
        value ever being reconstructable from the manifest."""
        redacted_segments: list[RedactedSegment] = []
        all_findings: list[RedactionFinding] = []
        counts: dict[str, int] = {}
        texts: list[str] = []
        for idx, seg in enumerate(segments):
            res = self.redact(seg.text)
            tagged = tuple(replace(f, segment_index=idx) for f in res.findings)
            all_findings.extend(tagged)
            for t, c in res.counts.items():
                counts[t] = counts.get(t, 0) + c
            texts.append(res.text)
            redacted_segments.append(
                RedactedSegment(
                    start=seg.start,
                    end=seg.end,
                    text=res.text,
                    speaker=seg.speaker,
                    confidence=seg.confidence,
                    redactions=tagged,
                )
            )
        joined = "\n".join(texts)
        combined = RedactionResult(
            text=joined,
            findings=tuple(all_findings),
            counts=counts,
            redacted_sha256=hashlib.sha256(joined.encode("utf-8")).hexdigest(),
            policy_version=POLICY_VERSION,
        )
        return redacted_segments, combined


# ---------------------------------------------------------------------------------------
# Declared policy — what is covered, and (equally load-bearing) what is not
# ---------------------------------------------------------------------------------------

COVERED: tuple[dict[str, str], ...] = (
    {"type": "EMAIL", "notes": "written form, plus spoken form ('jane dot doe at example dot com')"},
    {"type": "PHONE", "notes": "E.164/international, NANP separated + compact, UK/EU trunk, and cue-introduced numbers; all filtered to 7-15 digits"},
    {"type": "CREDIT_CARD", "notes": "13-19 digit runs validated with the Luhn checksum; non-Luhn runs are NOT redacted as cards"},
    {"type": "SPOKEN_CARD_NUMBER", "notes": "digit-word runs that reconstruct to a Luhn-valid 13-19 digit number"},
    {"type": "SPOKEN_NUMBER_SEQUENCE", "notes": f"runs of >= {MIN_SPOKEN_DIGITS} spoken digits including double/triple repeaters and mixed numeric output"},
    {"type": "IBAN", "notes": "ISO 13616 mod-97 validated"},
    {"type": "NATIONAL_ID", "notes": "US SSN with issuing-range exclusions, UK NINO, and cue-introduced identifiers (passport, licence, TFN, NHS, Aadhaar, Medicare)"},
    {"type": "DATE_OF_BIRTH", "notes": "numeric and textual dates preceded within 80 chars by a birth cue ('born', 'date of birth', 'DOB')"},
    {"type": "STREET_ADDRESS", "notes": "numbered street lines, PO boxes, UK postcodes, US state+ZIP"},
    {"type": "PERSON_NAME", "notes": "OPT-IN only (enable_person_names); requires spaCy + en_core_web_sm. NER recall is not exhaustive"},
)

NOT_COVERED: tuple[dict[str, str], ...] = (
    {"gap": "the audio itself", "notes": "redaction is TEXT-ONLY. The submitted audio is never modified and still contains the speaker's voice, which is itself biometric identifying data. Audio retention is the caller's responsibility."},
    {"gap": "spoken dates of birth", "notes": "'born on the fourth of July nineteen eighty two' is not matched; the date detectors are numeric/textual-written form only"},
    {"gap": "compound spoken numbers", "notes": "'twenty three forty five' (tens/teens/hundreds) is not expanded — only single-digit words zero-nine, plus double/triple repeaters"},
    {"gap": "non-English digit words", "notes": "the spoken-digit lexicon is English only"},
    {"gap": "spelled-out alphanumerics", "notes": "'A as in alpha, B as in bravo' NATO-style spellouts of a reference or licence plate are not reconstructed"},
    {"gap": "person names by default", "notes": "names are only removed when enable_person_names is set AND spaCy is installed; even then NER recall is partial and unmeasured here"},
    {"gap": "organisation / employer names", "notes": "not detected at all"},
    {"gap": "medical record numbers, policy numbers, account references", "notes": "no structural check exists for these; only caught incidentally if they are cue-introduced or long digit runs"},
    {"gap": "vehicle registrations / licence plates", "notes": "not detected"},
    {"gap": "IP addresses, device IDs, MAC addresses", "notes": "not detected — out of scope for a voice transcript, add detectors if text sources are mixed in"},
    {"gap": "quasi-identifiers", "notes": "a transcript can identify someone through combination (employer + role + rare condition) with no single redactable span. Redaction is not anonymisation and must not be relied on as such."},
    {"gap": "measured precision/recall", "notes": "there is NO labelled PII evaluation set in this estate, so no precision or recall figure is claimed for any detector above. The structural validators (Luhn, mod-97, SSN ranges) are exact by construction; everything else is untested against ground truth."},
)

POLICY: dict[str, object] = {
    "policy_version": POLICY_VERSION,
    "stage": "redaction runs BEFORE any downstream emission, storage, or analytics",
    "manifest_rule": "findings record type, detector and span only — removed values are NEVER echoed",
    "covered": list(COVERED),
    "not_covered": list(NOT_COVERED),
}
