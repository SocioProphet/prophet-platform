"""The vendored KnowledgeNugget contract: builders + hermetic, fail-closed validation.

Schema provenance (vendored so validation needs no network and no spec checkout):
    repo    SourceOS-Linux/sourceos-spec  (merged PR #210)
    path    schemas/KnowledgeNugget.json
    commit  ee7e43a42d5b3c30897eee296832ca127e8f6099
            (2026-07-29, "schemas: KnowledgeNugget + SemanticAction v0.1 — L2 content
            grain + typed-action registry")
    sha256  5b397e364ca5dbffea15da4bbcbedd6c62b6c5048ef28d8148739e03c13fcb1f
    spec    specs/knowledge-nugget-contract.md (v0.1.0, normative)
Re-vendor by copying the file from sourceos-spec and updating this block. The sha256 is
asserted at import: a drifted or hand-edited copy fails LOUDLY at startup, never
silently at emit time (apps/market-replay/src/market_replay/contract.py precedent) —
the whole claim of this service is "every nugget on the graph conforms to the estate
content-grain contract", so the contract itself must be tamper-evident.

WHAT A NUGGET IS (contract §1): one warrant-typed fragment of knowledge lifted from a
governed source, answering WHERE (sourceRef: docRef + character span + sha256 of the
source state), HOW (warrant: direct-quote | computed | inferred | model-generated, with
evidence refs + confidence) and WHAT (text, canonicalPayload, kkoTypeRefs).

THREE INVARIANTS JSON SCHEMA ALONE CANNOT CARRY, enforced here (contract §2):
  1. direct-quote EXACTNESS — span.end - span.start MUST equal len(text). The spec's own
     family validator asserts this across its examples; here it is asserted per nugget,
     at build AND at validate, because this service is the thing that mints them.
  2. direct-quote FIDELITY — text must be byte-identical to source_text[start:end] AND
     the contentHash must be the sha256 of that same source_text. A span length that
     happens to match is not a quote. This is the anti-laundering gate: you cannot claim
     `direct-quote` for text the source does not literally contain.
  3. span ORDERING — end >= start (schema types both as non-negative integers but says
     nothing about their relation).
The evidence-grounding rule (computed/inferred need >= 1 evidence ref) IS schema-carried
via warrant.allOf[0].if/then, so it is left to the validator — and negatively tested.

`model-generated` (contract §2, normative): produced by a model conditioned on the source
window and NOT warranted by it. sourceRef is REQUIRED anyway — it pins the conditioning
window. `build_model_generated` therefore takes the same mandatory source coordinates as
every other builder; there is no source-free path to a nugget in this module, so
unwarranted content cannot be laundered into source-warranted status by omission. The
one direction that would launder it — relabelling a model-generated nugget to a
source-warranted type — is refused by `retype_warrant`.
"""
from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from typing import Any, Iterable

from jsonschema import Draft202012Validator, ValidationError

SCHEMA_SHA256 = "5b397e364ca5dbffea15da4bbcbedd6c62b6c5048ef28d8148739e03c13fcb1f"
SPEC_VERSION = "0.1.0"                     # const in the schema — pinned, not guessed
URN_PREFIX = "urn:srcos:knowledge-nugget:"

WARRANT_TYPES = ("direct-quote", "computed", "inferred", "model-generated")
# The two warrants the schema's if/then requires evidence for. Kept as a constant so the
# tests assert against the same tuple the code reasons with.
DERIVED_WARRANTS = ("computed", "inferred")
SOURCE_WARRANTED = ("direct-quote", "computed", "inferred")

# Fixed producer identity (free-form refs are permitted at v0.1; URNs recommended).
CREATED_BY = "urn:srcos:agent:nugget-extractor"

# KKO reference concepts, taken from the TBox this estate already vendors
# (apps/sophos-reasoner/src/sophos_reasoner/data/kko-2.10.n3, namespace
# http://kbpedia.org/ontologies/kko#). Both classes are present in that file — these are
# not invented URIs. They are DECLARED type refs: nothing in this service resolves them
# against a loaded KKO (the platform-wide KKO TBox binding is a separate, tracked gap),
# so the graph carries the typing edge and the reasoner binds it when that lands.
KKO = "http://kbpedia.org/ontologies/kko#"
KKO_WRITTEN_INFO = KKO + "WrittenInfo"     # a text excerpt of a written document
KKO_QUANTITY = KKO + "Quantity"            # a normalized magnitude-with-unit

_SCHEMA_BYTES = (resources.files("nugget_extractor") / "schemas" / "KnowledgeNugget.json").read_bytes()
_actual = hashlib.sha256(_SCHEMA_BYTES).hexdigest()
if _actual != SCHEMA_SHA256:  # tamper-evident vendoring — see module docstring
    raise RuntimeError(
        f"vendored KnowledgeNugget.json drifted: sha256 {_actual} != pinned {SCHEMA_SHA256}; "
        "re-vendor from sourceos-spec and update contract.py provenance")

SCHEMA: dict[str, Any] = json.loads(_SCHEMA_BYTES)
VALIDATOR = Draft202012Validator(SCHEMA)

# URN local-id charset per the schema's id pattern: [A-Za-z0-9._~-].
_URN_UNSAFE = re.compile(r"[^A-Za-z0-9._~-]")
_DOCREF_RE = re.compile(r"^urn:srcos:[a-z0-9-]+:[A-Za-z0-9._~-]+$")


class NuggetError(ValueError):
    """A nugget could not be built or is not what it claims. Never raised past the
    emitter's fail-closed gate — counted and logged there, never emitted."""


def content_hash(source_text: str) -> str:
    """sha256-<64hex> over the UTF-8 bytes of the hashed source text.

    Spans are CHARACTER offsets into `source_text`; the hash is over its UTF-8 encoding.
    That is the spec's model (contract §6: "span offsets are character-based over the
    hashed source text"), and pinning both together is what stops offsets drifting."""
    return "sha256-" + hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def doc_urn(kind: str, local: str) -> str:
    """Build a schema-legal docRef URN: urn:srcos:<kind>:<sanitized local id>."""
    return f"urn:srcos:{_URN_UNSAFE.sub('-', kind).lower()}:{_URN_UNSAFE.sub('-', local)}"


def local_id(doc_ref: str, src_hash: str, ordinal: int) -> str:
    """Deterministic, content-addressed nugget local id.

    A function of (docRef, source content hash, ordinal) ONLY — so re-extracting the same
    document bytes mints the same nugget URNs, the graph node upserts in place, and a
    replay after a restart can never fork identity. Identity is stable and never reused
    (schema `id` invariant); supersession is a provenance link, never an id rewrite."""
    digest = hashlib.sha256(f"{doc_ref}|{src_hash}".encode("utf-8")).hexdigest()[:12]
    return f"nug-{digest}-{ordinal:06d}"


def _base(*, doc_ref: str, src_hash: str, start: int, end: int, page: int | None,
          ordinal: int, text: str, wall_time: str, logical_time: int,
          kko_type_refs: Iterable[str], policy_labels: Iterable[str],
          provenance: list[dict[str, str]] | None) -> dict[str, Any]:
    """The fields every warrant type shares. sourceRef is assembled HERE, for every
    warrant type — including model-generated — so there is no code path to a nugget
    without source coordinates."""
    if not _DOCREF_RE.match(doc_ref):
        raise NuggetError(f"docRef {doc_ref!r} does not match the schema's urn:srcos: pattern")
    if end < start:
        raise NuggetError(f"span end {end} < start {start}")
    span: dict[str, Any] = {"start": int(start), "end": int(end)}
    if page is not None:
        span["page"] = int(page)
    nugget: dict[str, Any] = {
        "id": URN_PREFIX + local_id(doc_ref, src_hash, ordinal),
        "type": "KnowledgeNugget",
        "specVersion": SPEC_VERSION,
        "sourceRef": {"docRef": doc_ref, "span": span, "contentHash": src_hash},
        "text": text,
        "kkoTypeRefs": sorted(set(kko_type_refs)),
        "policyLabels": sorted(set(policy_labels)),
        "createdBy": CREATED_BY,
        "wallTime": wall_time,
        "logicalTime": int(logical_time),
    }
    if provenance:
        nugget["provenance"] = provenance
    return nugget


def build_direct_quote(*, doc_ref: str, source_text: str, src_hash: str, start: int,
                       end: int, page: int | None, ordinal: int, wall_time: str,
                       logical_time: int, run_ref: str,
                       kko_type_refs: Iterable[str] = (KKO_WRITTEN_INFO,),
                       policy_labels: Iterable[str] = (),
                       confidence: float = 1.0) -> dict[str, Any]:
    """text IS the source span — so it is not passed in, it is CUT from the source.

    The only way to mint a direct-quote here is to hand over the source text the hash
    was taken from; the quote is then `source_text[start:end]` by construction, which
    makes invariants 1 and 2 true at build time rather than merely checked afterwards.
    confidence defaults to 1.0: a verbatim cut is not a guess. (Admissibility is still a
    function of warrant type first — contract §2.)"""
    if src_hash != content_hash(source_text):
        raise NuggetError("contentHash does not match sha256 of the supplied source text")
    if not 0 <= start <= end <= len(source_text):
        raise NuggetError(f"span [{start},{end}) out of range for source of {len(source_text)} chars")
    text = source_text[start:end]
    if not text:
        raise NuggetError("a direct-quote span selects no text")
    nugget = _base(doc_ref=doc_ref, src_hash=src_hash, start=start, end=end, page=page,
                   ordinal=ordinal, text=text, wall_time=wall_time,
                   logical_time=logical_time, kko_type_refs=kko_type_refs,
                   policy_labels=policy_labels,
                   provenance=[{"rel": "derived_from", "ref": doc_ref},
                               {"rel": "extracted_by", "ref": run_ref}])
    # direct-quote is grounded by sourceRef itself (contract §2) — the extraction run is
    # still cited, so the receipt chain is reachable from the nugget.
    nugget["warrant"] = {"type": "direct-quote", "evidence": [run_ref],
                         "confidence": float(confidence)}
    return nugget


def build_computed(*, doc_ref: str, src_hash: str, start: int, end: int,
                   page: int | None, ordinal: int, text: str, wall_time: str,
                   logical_time: int, evidence: list[str],
                   canonical_payload: dict[str, Any],
                   kko_type_refs: Iterable[str] = (KKO_QUANTITY,),
                   policy_labels: Iterable[str] = (),
                   confidence: float = 0.95) -> dict[str, Any]:
    """Derived by deterministic computation over cited source values.

    `evidence` is mandatory and non-empty at the Python boundary as well as in the schema
    — "a derivation with no cited inputs is not a derivation" (contract §2). The cited
    refs are the nuggets the computation consumed, so the warrant graph is walkable.
    canonicalPayload must declare its normalizationRegime (schema invariant on the
    field)."""
    if not evidence:
        raise NuggetError("a computed warrant must cite at least one evidence ref")
    if "normalizationRegime" not in canonical_payload:
        raise NuggetError("canonicalPayload must declare its normalizationRegime")
    nugget = _base(doc_ref=doc_ref, src_hash=src_hash, start=start, end=end, page=page,
                   ordinal=ordinal, text=text, wall_time=wall_time,
                   logical_time=logical_time, kko_type_refs=kko_type_refs,
                   policy_labels=policy_labels,
                   provenance=[{"rel": "derived_from", "ref": e} for e in evidence])
    nugget["warrant"] = {"type": "computed", "evidence": list(dict.fromkeys(evidence)),
                         "confidence": float(confidence)}
    nugget["canonicalPayload"] = canonical_payload
    return nugget


def build_inferred(*, doc_ref: str, src_hash: str, start: int, end: int,
                   page: int | None, ordinal: int, text: str, wall_time: str,
                   logical_time: int, evidence: list[str],
                   kko_type_refs: Iterable[str] = (),
                   policy_labels: Iterable[str] = (),
                   confidence: float = 0.7) -> dict[str, Any]:
    """Follows by stated inference from cited premises — same grounding rule as computed.

    NOT produced by this service's text extractor (it runs no inference engine); the
    builder exists so the contract is complete and exercised, and so a caller that DOES
    have premises (the reasoning fabric) mints inferred nuggets through the same
    fail-closed gate rather than a second, looser one."""
    if not evidence:
        raise NuggetError("an inferred warrant must cite at least one evidence ref")
    nugget = _base(doc_ref=doc_ref, src_hash=src_hash, start=start, end=end, page=page,
                   ordinal=ordinal, text=text, wall_time=wall_time,
                   logical_time=logical_time, kko_type_refs=kko_type_refs,
                   policy_labels=policy_labels,
                   provenance=[{"rel": "derived_from", "ref": e} for e in evidence])
    nugget["warrant"] = {"type": "inferred", "evidence": list(dict.fromkeys(evidence)),
                         "confidence": float(confidence)}
    return nugget


def build_model_generated(*, doc_ref: str, src_hash: str, window_start: int,
                          window_end: int, page: int | None, ordinal: int, text: str,
                          wall_time: str, logical_time: int, generator_ref: str,
                          kko_type_refs: Iterable[str] = (),
                          policy_labels: Iterable[str] = (),
                          confidence: float = 0.5) -> dict[str, Any]:
    """Produced by a model conditioned on a source window and NOT warranted by it.

    The window is MANDATORY: `model-generated` means unwarranted-by-span, never
    source-free (contract §2). sourceRef.span records the conditioning window the
    generation was given, sourceRef.contentHash sha256-pins the exact source state that
    window indexes into — so "what was this generated from?" is answerable, and the
    admissibility discount is applied to a nugget whose provenance is fully stated.

    NOT produced by this service (it calls no model). Exists so any producer that does
    must state its window, and so the emitter's laundering test has a real object."""
    nugget = _base(doc_ref=doc_ref, src_hash=src_hash, start=window_start,
                   end=window_end, page=page, ordinal=ordinal, text=text,
                   wall_time=wall_time, logical_time=logical_time,
                   kko_type_refs=kko_type_refs, policy_labels=policy_labels,
                   provenance=[{"rel": "conditioned_on", "ref": doc_ref},
                               {"rel": "generated_by", "ref": generator_ref}])
    # evidence MAY be empty here — "which is exactly why it is admissibility-discounted".
    nugget["warrant"] = {"type": "model-generated", "evidence": [],
                         "confidence": float(confidence)}
    return nugget


def retype_warrant(nugget: dict[str, Any], new_type: str) -> dict[str, Any]:
    """The ONE transform that could launder a warrant — and it refuses to.

    Contract §2, normative: "no downstream transform may launder a model-generated nugget
    into a source-warranted one". A model-generated nugget is terminal: nothing in this
    process can promote it to direct-quote / computed / inferred. (Demotion TO
    model-generated is allowed — that only ever weakens a claim.)"""
    if new_type not in WARRANT_TYPES:
        raise NuggetError(f"warrant type {new_type!r} is outside the closed v0.1 taxonomy")
    current = nugget["warrant"]["type"]
    if current == "model-generated" and new_type in SOURCE_WARRANTED:
        raise NuggetError(
            "refusing to launder a model-generated nugget into source-warranted status "
            f"({current} -> {new_type}); the taxonomy is one-way by contract")
    out = json.loads(json.dumps(nugget))
    out["warrant"]["type"] = new_type
    return out


def validate_nugget(nugget: dict[str, Any], source_text: str | None = None) -> None:
    """THE fail-closed gate. Raises on any non-conformance; the caller counts and drops.

    Schema first (closed objects, pinned specVersion, closed warrant enum, sha256-only
    content hash, the computed/inferred evidence if/then), then the three invariants the
    schema cannot carry. `source_text`, when supplied, upgrades the direct-quote check
    from "the span is the right LENGTH" to "the text IS what the source says" — the
    difference between an arithmetic coincidence and a quote."""
    VALIDATOR.validate(nugget)

    span = nugget["sourceRef"]["span"]
    start, end = span["start"], span["end"]
    if end < start:
        raise ValidationError(f"span.end ({end}) must be >= span.start ({start})")

    warrant = nugget["warrant"]["type"]
    if warrant == "direct-quote":
        if end - start != len(nugget["text"]):
            raise ValidationError(
                f"a direct-quote span must be exactly as long as its text: "
                f"span is {end - start} chars, text is {len(nugget['text'])}")
        if source_text is not None:
            if nugget["sourceRef"]["contentHash"] != content_hash(source_text):
                raise ValidationError(
                    "contentHash does not match the sha256 of the source text the span "
                    "indexes into — the span cannot be checked against a different source")
            if source_text[start:end] != nugget["text"]:
                raise ValidationError(
                    "direct-quote text is not what the source span says — refusing a "
                    "quote the document does not contain")
    # computed/inferred evidence grounding is schema-enforced (warrant.allOf[0]); asserted
    # here too so the failure names itself instead of surfacing as a bare if/then miss.
    if warrant in DERIVED_WARRANTS and not nugget["warrant"]["evidence"]:
        raise ValidationError(f"a {warrant} warrant must cite at least one evidence ref")


def flatten(nugget: dict[str, Any], ingest_time: str) -> dict[str, Any]:
    """The graph-node property projection: flat scalars for querying, PLUS the full
    validated nugget as canonical JSON — so the graph carries the spec-conformant OBJECT,
    not just a lossy projection (market-replay precedent).

    `warrantType` is a first-class column and `modelGenerated` a boolean, because the
    normative design rule is that model-generated content stays VISIBLY distinguishable
    on every downstream surface: a ranker that never parses the JSON blob still cannot
    miss it."""
    warrant = nugget["warrant"]
    src = nugget["sourceRef"]
    return {
        "nuggetId": nugget["id"],
        "schemaVersion": nugget["specVersion"],
        "warrantType": warrant["type"],
        "modelGenerated": warrant["type"] == "model-generated",
        "sourceWarranted": warrant["type"] in SOURCE_WARRANTED,
        "confidence": warrant["confidence"],
        "evidenceCount": len(warrant["evidence"]),
        "docRef": src["docRef"],
        "contentHash": src["contentHash"],
        "spanStart": src["span"]["start"],
        "spanEnd": src["span"]["end"],
        "page": src["span"].get("page"),
        "text": nugget["text"],
        "textLength": len(nugget["text"]),
        "kkoTypeRefs": ",".join(nugget.get("kkoTypeRefs", [])),
        "createdBy": nugget["createdBy"],
        "policyLabels": ",".join(nugget.get("policyLabels", [])),
        "wallTime": nugget["wallTime"],
        "logicalTime": nugget["logicalTime"],
        "ingestTime": ingest_time,
        "nugget": json.dumps(nugget, sort_keys=True, ensure_ascii=False),
    }


def batch_hash(nuggets: list[dict[str, Any]]) -> str:
    """sha256 over the canonical JSON of the emitted batch, in emission order — the
    coordinate the compute-gateway receipt binds into inputs_sha, so the seal covers
    exactly what went onto the graph."""
    body = "\n".join(json.dumps(n, sort_keys=True, ensure_ascii=False) for n in nuggets)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def startup_check() -> None:
    """Boot-time fail-closed gate: the vendored schema hash is already asserted at import;
    here the schema must be a valid Draft 2020-12 document AND a probe nugget of every
    warrant type, built by THIS code, must validate — and the laundering refusal must
    hold. Any drift kills the process at boot, before a single nugget reaches the graph."""
    Draft202012Validator.check_schema(SCHEMA)
    src = "Network sales grew 22.6%. Probe."
    h = content_hash(src)
    doc = doc_urn("document", "startup-probe")
    quote = build_direct_quote(doc_ref=doc, source_text=src, src_hash=h, start=0, end=25,
                               page=1, ordinal=0, wall_time="2026-07-29T00:00:00.000Z",
                               logical_time=0, run_ref="urn:srcos:run:startup-probe")
    validate_nugget(quote, source_text=src)
    computed = build_computed(doc_ref=doc, src_hash=h, start=0, end=25, page=1, ordinal=1,
                              text="Normalized 22.6 percent.",
                              wall_time="2026-07-29T00:00:00.000Z", logical_time=1,
                              evidence=[quote["id"]],
                              canonical_payload={"normalizationRegime": "probe@v1",
                                                 "value": 22.6, "unit": "percent"})
    validate_nugget(computed)
    inferred = build_inferred(doc_ref=doc, src_hash=h, start=0, end=25, page=1, ordinal=2,
                              text="Probe inference.", wall_time="2026-07-29T00:00:00.000Z",
                              logical_time=2, evidence=[quote["id"]])
    validate_nugget(inferred)
    generated = build_model_generated(doc_ref=doc, src_hash=h, window_start=0,
                                      window_end=len(src), page=1, ordinal=3,
                                      text="Probe synthesis.",
                                      wall_time="2026-07-29T00:00:00.000Z", logical_time=3,
                                      generator_ref="urn:srcos:run:startup-probe")
    validate_nugget(generated)
    try:
        retype_warrant(generated, "direct-quote")
    except NuggetError:
        return
    raise RuntimeError("laundering guard is not in force — model-generated was retyped "
                       "to direct-quote; refusing to start")


__all__ = ["SCHEMA", "SCHEMA_SHA256", "SPEC_VERSION", "URN_PREFIX", "WARRANT_TYPES",
           "DERIVED_WARRANTS", "SOURCE_WARRANTED", "CREATED_BY", "KKO",
           "KKO_WRITTEN_INFO", "KKO_QUANTITY", "NuggetError", "content_hash", "doc_urn",
           "local_id", "build_direct_quote", "build_computed", "build_inferred",
           "build_model_generated", "retype_warrant", "validate_nugget", "flatten",
           "batch_hash", "startup_check"]
