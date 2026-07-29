"""Conformance vectors for the KnowledgeNugget contract — positive AND negative.

The negatives are the point. A validator that has only ever been shown valid documents
proves nothing; each case below states the rule it exists to break, and the test FAILS if
the document is accepted. Five of them are the sourceos-spec's own
fixtures/knowledge-nugget/conformance.json cases carried verbatim, so our vendored copy
of the schema is proven to reject exactly what the spec's own family validator rejects;
the rest cover the invariants JSON Schema cannot carry and the laundering guard.
"""
from __future__ import annotations

import copy
import hashlib
import json

import pytest
from jsonschema import ValidationError

from nugget_extractor import contract

SRC = ("Network sales grew 22.6% to $1,138.9 million.\n\n"
       "Comparable sales growth was 9.4 per cent across the Australian segment.")
HASH = contract.content_hash(SRC)
DOC = "urn:srcos:dataset:gyg_asx_fy2025_annual_report"
RUN = "urn:srcos:run:ifm_extract_run_000412"
WHEN = "2026-07-29T09:15:00.000Z"


def quote(start: int = 0, end: int = 44, ordinal: int = 0) -> dict:
    return contract.build_direct_quote(
        doc_ref=DOC, source_text=SRC, src_hash=HASH, start=start, end=end, page=1,
        ordinal=ordinal, wall_time=WHEN, logical_time=ordinal, run_ref=RUN)


# ───────────────────────── the vendored schema itself ─────────────────────────
def test_vendored_schema_matches_the_pinned_sha256():
    """The import-time assert is the real gate; this proves the pin is the file's actual
    hash and not a stale constant that happens to be unreachable."""
    blob = (contract.resources.files("nugget_extractor") / "schemas"
            / "KnowledgeNugget.json").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == contract.SCHEMA_SHA256


def test_vendored_schema_is_the_v0_1_0_contract():
    assert contract.SCHEMA["title"] == "KnowledgeNugget"
    assert contract.SCHEMA["properties"]["specVersion"]["const"] == "0.1.0"
    assert contract.SCHEMA["additionalProperties"] is False
    assert (contract.SCHEMA["properties"]["warrant"]["properties"]["type"]["enum"]
            == list(contract.WARRANT_TYPES))
    assert "sourceRef" in contract.SCHEMA["required"]


def test_startup_check_passes():
    contract.startup_check()


# ───────────────────────── positive: the spec's own examples ─────────────────────────
# Carried verbatim from SourceOS-Linux/sourceos-spec examples/ at commit ee7e43a4. If our
# vendored schema ever stops accepting the spec's canonical examples, the vendoring has
# drifted in a way the sha check alone would not explain.
SPEC_EXAMPLE_DIRECT_QUOTE = {
    "id": "urn:srcos:knowledge-nugget:gyg_fy2025_network_sales_quote_0001",
    "type": "KnowledgeNugget", "specVersion": "0.1.0",
    "sourceRef": {"docRef": "urn:srcos:dataset:gyg_asx_fy2025_annual_report",
                  "span": {"start": 48210, "end": 48323, "page": 74},
                  "contentHash": "sha256-0d863a1cca056ffe7948415a29d795c2581fbfcda7e3e30f544cd078333d1337"},
    "warrant": {"type": "direct-quote",
                "evidence": ["urn:srcos:prov:ifm_extract_run_000412"], "confidence": 0.99},
    "text": ("Network sales grew 22.6% to $1,138.9 million, with comparable sales growth "
             "of 9.4% across the Australian segment."),
    "kkoTypeRefs": ["http://kbpedia.org/kko/rc/Business",
                    "https://schemas.srcos.ai/ont/ifm/FilingMetricObservation"],
    "canonicalPayload": {"metric": "network_sales", "value": 1138900000, "unit": "AUD",
                         "growthPct": 22.6, "normalizationRegime": "ifm-metric-v1"},
    "provenance": [{"rel": "derived_from", "ref": "urn:srcos:dataset:gyg_asx_fy2025_annual_report"},
                   {"rel": "extracted_by", "ref": "urn:srcos:run:ifm_extract_run_000412"}],
    "policyLabels": ["source:public-filing"],
    "createdBy": "urn:srcos:agent:ifm_extractor_v2",
    "wallTime": "2026-07-29T09:15:00.000Z", "logicalTime": 4021,
}
SPEC_EXAMPLE_MODEL_GENERATED = {
    "id": "urn:srcos:knowledge-nugget:gyg_fy2026_outlook_synthesis_0007",
    "type": "KnowledgeNugget", "specVersion": "0.1.0",
    "sourceRef": {"docRef": "urn:srcos:dataset:gyg_asx_fy2025_annual_report",
                  "span": {"start": 46800, "end": 52400, "page": 73},
                  "contentHash": "sha256-b8b7fefebb4e8f612ea0a89fd6f465a9c0e57a09630ce7c565e9c5de86a7fc92"},
    "warrant": {"type": "model-generated", "evidence": [], "confidence": 0.62},
    "text": ("Management appears to expect continued store rollout to sustain double-digit "
             "network sales growth into FY2026."),
    "kkoTypeRefs": ["http://kbpedia.org/kko/rc/Business"],
    "provenance": [{"rel": "conditioned_on", "ref": "urn:srcos:dataset:gyg_asx_fy2025_annual_report"},
                   {"rel": "generated_by", "ref": "urn:srcos:run:ifm_synthesis_run_000413"}],
    "policyLabels": ["source:public-filing"],
    "createdBy": "urn:srcos:agent:ifm_synthesizer_v1",
    "wallTime": "2026-07-29T09:16:30.000Z", "logicalTime": 4022,
}


@pytest.mark.parametrize("example", [SPEC_EXAMPLE_DIRECT_QUOTE, SPEC_EXAMPLE_MODEL_GENERATED],
                         ids=["spec-example-direct-quote", "spec-example-model-generated"])
def test_spec_canonical_examples_validate(example):
    contract.validate_nugget(example)


def test_spec_direct_quote_example_satisfies_the_exactness_rule():
    span = SPEC_EXAMPLE_DIRECT_QUOTE["sourceRef"]["span"]
    assert span["end"] - span["start"] == len(SPEC_EXAMPLE_DIRECT_QUOTE["text"])


# ───────────────────────── positive: what this service builds ─────────────────────────
def test_direct_quote_text_is_cut_from_the_source_not_supplied():
    n = quote()
    contract.validate_nugget(n, source_text=SRC)
    assert n["text"] == SRC[0:44]
    assert n["sourceRef"]["span"]["end"] - n["sourceRef"]["span"]["start"] == len(n["text"])
    assert n["warrant"]["type"] == "direct-quote"


def test_every_warrant_type_carries_a_source_ref_including_model_generated():
    built = [
        quote(),
        contract.build_computed(doc_ref=DOC, src_hash=HASH, start=0, end=44, page=1,
                                ordinal=1, text="Normalized 22.6 percent.", wall_time=WHEN,
                                logical_time=1, evidence=[quote()["id"]],
                                canonical_payload={"normalizationRegime": "t@v1", "value": 22.6}),
        contract.build_inferred(doc_ref=DOC, src_hash=HASH, start=0, end=44, page=1,
                                ordinal=2, text="Margins likely expanded.", wall_time=WHEN,
                                logical_time=2, evidence=[quote()["id"]]),
        contract.build_model_generated(doc_ref=DOC, src_hash=HASH, window_start=0,
                                       window_end=len(SRC), page=1, ordinal=3,
                                       text="Outlook synthesis.", wall_time=WHEN,
                                       logical_time=3, generator_ref="urn:srcos:run:x"),
    ]
    assert {n["warrant"]["type"] for n in built} == set(contract.WARRANT_TYPES)
    for n in built:
        contract.validate_nugget(n)
        # THE rule: model-generated means unwarranted BY SPAN, never source-free.
        assert n["sourceRef"]["docRef"] and n["sourceRef"]["contentHash"].startswith("sha256-")
        assert n["sourceRef"]["span"]["end"] >= n["sourceRef"]["span"]["start"]


def test_nugget_identity_is_content_addressed_and_stable():
    """Same document, same span, same ordinal ⇒ the same URN on every run and after every
    restart. This is what makes re-submission idempotent (graph nodes upsert)."""
    assert quote()["id"] == quote()["id"]
    assert quote(ordinal=1)["id"] != quote(ordinal=0)["id"]
    other = contract.build_direct_quote(
        doc_ref="urn:srcos:dataset:other", source_text=SRC, src_hash=HASH, start=0, end=44,
        page=1, ordinal=0, wall_time=WHEN, logical_time=0, run_ref=RUN)
    assert other["id"] != quote()["id"]


def test_flatten_keeps_model_generated_visible_as_a_first_class_field():
    """The normative design rule is downstream VISIBILITY. A ranker reading only the flat
    projection must still be able to discount it without parsing the JSON blob."""
    gen = contract.build_model_generated(doc_ref=DOC, src_hash=HASH, window_start=0,
                                         window_end=len(SRC), page=1, ordinal=0,
                                         text="Synthesis.", wall_time=WHEN, logical_time=0,
                                         generator_ref="urn:srcos:run:x")
    flat = contract.flatten(gen, ingest_time=WHEN)
    assert flat["warrantType"] == "model-generated"
    assert flat["modelGenerated"] is True and flat["sourceWarranted"] is False
    assert json.loads(flat["nugget"]) == gen           # the full object travels too
    flat_q = contract.flatten(quote(), ingest_time=WHEN)
    assert flat_q["modelGenerated"] is False and flat_q["sourceWarranted"] is True


def test_batch_hash_is_order_sensitive_and_content_sensitive():
    a, b = quote(0, 44, 0), quote(46, 60, 1)
    assert contract.batch_hash([a, b]) != contract.batch_hash([b, a])
    assert contract.batch_hash([a, b]) == contract.batch_hash([a, b])


# ───────────────────────── NEGATIVE VECTORS ─────────────────────────
def _reject(doc: dict, source_text: str | None = None) -> str:
    with pytest.raises((ValidationError, contract.NuggetError)) as e:
        contract.validate_nugget(doc, source_text=source_text)
    return str(e.value)


def test_negative_direct_quote_span_longer_than_its_text():
    """THE exactness invariant. A span that claims more characters than the text it
    carries is not a quote — it is a citation of something the nugget does not show."""
    bad = quote()
    bad["sourceRef"]["span"]["end"] += 10
    assert "direct-quote span must be exactly as long" in _reject(bad)


def test_negative_direct_quote_span_shorter_than_its_text():
    bad = quote()
    bad["sourceRef"]["span"]["end"] -= 5
    assert "direct-quote span must be exactly as long" in _reject(bad)


def test_negative_direct_quote_text_the_source_does_not_contain():
    """Length alone is an arithmetic coincidence. Checked against the source, a rewritten
    quote of the SAME LENGTH is still refused — this is the anti-laundering gate."""
    bad = quote()
    bad["text"] = "X" * len(bad["text"])
    assert "not what the source span says" in _reject(bad, source_text=SRC)


def test_negative_direct_quote_against_a_different_source():
    bad = quote()
    assert "contentHash does not match" in _reject(bad, source_text=SRC + " tampered")


def test_negative_evidence_free_computed():
    """Schema if/then: a derivation with no cited inputs is not a derivation."""
    bad = quote()
    bad["warrant"] = {"type": "computed", "evidence": [], "confidence": 0.9}
    bad["canonicalPayload"] = {"normalizationRegime": "t@v1", "value": 1}
    _reject(bad)


def test_negative_evidence_free_inferred():
    bad = quote()
    bad["warrant"] = {"type": "inferred", "evidence": [], "confidence": 0.8}
    _reject(bad)


def test_negative_missing_source_ref():
    """sourceRef is REQUIRED for every warrant type — there is no source-free nugget."""
    for warrant in ({"type": "direct-quote", "evidence": [], "confidence": 0.9},
                    {"type": "model-generated", "evidence": [], "confidence": 0.5}):
        bad = quote()
        bad["warrant"] = warrant
        del bad["sourceRef"]
        assert "sourceRef" in _reject(bad)


def test_negative_builders_cannot_produce_a_source_free_nugget():
    """Not merely rejected downstream — unconstructible. Every builder takes doc_ref and
    src_hash as required keyword arguments, so omission is a TypeError at the call site."""
    with pytest.raises(TypeError):
        contract.build_model_generated(window_start=0, window_end=5, page=1, ordinal=0,
                                       text="t", wall_time=WHEN, logical_time=0,
                                       generator_ref="urn:srcos:run:x")  # no doc_ref/src_hash
    with pytest.raises(contract.NuggetError):
        contract.build_direct_quote(doc_ref="not-a-urn", source_text=SRC, src_hash=HASH,
                                    start=0, end=4, page=1, ordinal=0, wall_time=WHEN,
                                    logical_time=0, run_ref=RUN)


def test_negative_laundering_model_generated_into_source_warranted():
    """Contract §2, normative: no downstream transform may launder a model-generated
    nugget into a source-warranted one."""
    gen = contract.build_model_generated(doc_ref=DOC, src_hash=HASH, window_start=0,
                                         window_end=len(SRC), page=1, ordinal=0,
                                         text="Synthesis.", wall_time=WHEN, logical_time=0,
                                         generator_ref="urn:srcos:run:x")
    for target in contract.SOURCE_WARRANTED:
        with pytest.raises(contract.NuggetError, match="refusing to launder"):
            contract.retype_warrant(gen, target)
    # Demotion only ever weakens a claim, so it is permitted.
    assert contract.retype_warrant(quote(), "model-generated")["warrant"]["type"] == \
        "model-generated"
    assert quote()["warrant"]["type"] == "direct-quote"   # and the original is untouched


def test_negative_warrant_type_outside_the_closed_taxonomy():
    bad = quote()
    bad["warrant"]["type"] = "hearsay"
    _reject(bad)
    with pytest.raises(contract.NuggetError, match="outside the closed"):
        contract.retype_warrant(quote(), "hearsay")


def test_negative_unknown_top_level_property():
    bad = quote()
    bad["vibeScore"] = 11
    _reject(bad)


def test_negative_non_sha256_content_hash():
    bad = quote()
    bad["sourceRef"]["contentHash"] = "md5-d41d8cd98f00b204e9800998ecf8427e"
    _reject(bad)


def test_negative_spec_version_drift():
    bad = quote()
    bad["specVersion"] = "0.2.0"
    _reject(bad)


def test_negative_span_end_before_start():
    bad = copy.deepcopy(SPEC_EXAMPLE_MODEL_GENERATED)
    bad["sourceRef"]["span"] = {"start": 500, "end": 100}
    assert "must be >= span.start" in _reject(bad)


def test_negative_id_outside_the_urn_pattern():
    bad = quote()
    bad["id"] = "nugget-1"
    _reject(bad)


def test_negative_builder_refuses_a_computed_without_evidence():
    with pytest.raises(contract.NuggetError, match="at least one evidence ref"):
        contract.build_computed(doc_ref=DOC, src_hash=HASH, start=0, end=4, page=1,
                                ordinal=0, text="t", wall_time=WHEN, logical_time=0,
                                evidence=[], canonical_payload={"normalizationRegime": "x"})
    with pytest.raises(contract.NuggetError, match="at least one evidence ref"):
        contract.build_inferred(doc_ref=DOC, src_hash=HASH, start=0, end=4, page=1,
                                ordinal=0, text="t", wall_time=WHEN, logical_time=0,
                                evidence=[])


def test_negative_computed_payload_without_a_normalization_regime():
    with pytest.raises(contract.NuggetError, match="normalizationRegime"):
        contract.build_computed(doc_ref=DOC, src_hash=HASH, start=0, end=4, page=1,
                                ordinal=0, text="t", wall_time=WHEN, logical_time=0,
                                evidence=[RUN], canonical_payload={"value": 1})


def test_negative_direct_quote_span_out_of_range_or_empty():
    with pytest.raises(contract.NuggetError, match="out of range"):
        quote(0, len(SRC) + 5)
    with pytest.raises(contract.NuggetError, match="selects no text"):
        quote(5, 5)
