"""Pipeline tests — end-to-end on the fixture, and the ordering guarantee.

The load-bearing tests here are the ordering ones. "Redaction runs before anything
downstream sees the text" is a claim, and a claim in a governance framework is worth
exactly what its test is worth. These check it four ways:

  * a downstream sink registered on the pipeline receives redacted segments and nothing else
  * no raw PII value appears anywhere in the serialized result, at any depth
  * the audit log records redact before emit and before store
  * the store refuses a result whose redaction stage did not run
"""
from __future__ import annotations

import json

import pytest

from voice_substrate.asr import FixtureAdapter
from voice_substrate.diarization import HeuristicDiarizer, NullDiarizer
from voice_substrate.pipeline import VoicePipeline, default_pipeline, redaction_precedes_emission
from voice_substrate.redaction import RedactionPolicy
from voice_substrate.storage import (
    FilesystemTranscriptStore,
    InMemoryTranscriptStore,
    UnredactedWriteRefused,
)
from voice_substrate.types import (
    AuditEvent,
    PipelineResult,
    RedactedSegment,
    TranscriptSegment,
)

# Values present in the pii_sampler fixture. If any of these survive to an output, the
# substrate has leaked.
FIXTURE_SECRETS = [
    "07700 900482",
    "7946 0958",
    "jane dot harper at example dot com",
    "j.harper@contoso.co.uk",
    "14/03/1979",
    "123-45-6789",
    "221B Baker Street",
    "NW1 6XE",
    "PO Box 4471",
    "4539 1488 0343 6467",
    "GB82 WEST 12345698765432",
    "double four seven three one nine two eight",
    "(413) 555-0134",
    "1600 Pennsylvania Avenue",
]


@pytest.fixture()
def result():
    return default_pipeline().run(metadata={"call_id": "test-001"})


# ---------------------------------------------------------------------------------------
# End-to-end on the fixture
# ---------------------------------------------------------------------------------------


def test_fixture_pipeline_runs_end_to_end_without_any_speech_dependency(result):
    assert len(result.segments) == 15
    assert result.redaction_applied is True
    assert result.asr_adapter == "fixture:pii_sampler"
    assert result.diarizer == "heuristic_turn_alternation"


def test_every_covered_class_in_the_fixture_is_caught(result):
    counts = result.redaction.counts
    for expected in ("EMAIL", "PHONE", "CREDIT_CARD", "IBAN", "NATIONAL_ID",
                     "DATE_OF_BIRTH", "STREET_ADDRESS", "SPOKEN_NUMBER_SEQUENCE"):
        assert counts.get(expected, 0) >= 1, f"{expected} not caught: {counts}"


def test_the_non_luhn_reference_in_the_fixture_survives(result):
    """The fixture's last line carries a 16-digit invoice reference that fails Luhn. It
    must NOT be redacted as a card — that is the false-positive control, in the fixture."""
    assert "4539148803436460" in result.segments[-1].text


def test_speakers_are_labelled_and_alternate(result):
    speakers = {s.speaker for s in result.segments}
    assert speakers == {"speaker_0", "speaker_1"}


def test_result_warns_that_no_real_asr_ran(result):
    joined = " ".join(result.warnings)
    assert "NO REAL ASR" in joined
    assert "NOT speaker identification" in joined
    assert result.to_dict()["provenance"]["real_asr"] is False


def test_clean_fixture_produces_no_findings():
    r = default_pipeline(fixture="clean_meeting").run()
    assert r.redaction.total == 0
    assert r.redaction_applied is True  # ran, found nothing — not the same as "skipped"


def test_segments_carry_their_own_findings(result):
    tagged = [f for s in result.segments for f in s.redactions]
    assert len(tagged) == result.redaction.total
    assert all(f.segment_index is not None for f in tagged)
    for idx, seg in enumerate(result.segments):
        for f in seg.redactions:
            assert f.segment_index == idx


# ---------------------------------------------------------------------------------------
# Ordering: redaction precedes ANY downstream emission
# ---------------------------------------------------------------------------------------


def test_downstream_sink_only_ever_receives_redacted_segments():
    seen: list[object] = []
    pipe = VoicePipeline(
        asr=FixtureAdapter(fixture="pii_sampler"),
        diarizer=HeuristicDiarizer(),
        emit_sinks=[seen.append],
    )
    pipe.run()
    assert len(seen) == 1
    delivered = seen[0]
    assert all(isinstance(s, RedactedSegment) for s in delivered)
    assert not any(isinstance(s, TranscriptSegment) for s in delivered)
    blob = " ".join(s.text for s in delivered)
    for secret in FIXTURE_SECRETS:
        assert secret not in blob, f"raw value reached a downstream sink: {secret[:6]}..."


def test_no_raw_value_survives_anywhere_in_the_serialized_result(result):
    """Whole-object sweep, not just the segment text: audit log, manifest, provenance,
    warnings — everything the caller receives."""
    blob = json.dumps(result.to_dict())
    for secret in FIXTURE_SECRETS:
        assert secret not in blob
        assert secret.replace(" ", "") not in blob.replace(" ", "")


def test_audit_log_records_redact_before_emit_and_store():
    store = InMemoryTranscriptStore()
    pipe = VoicePipeline(asr=FixtureAdapter(), diarizer=NullDiarizer(), store=store)
    r = pipe.run()
    stages = [e.stage for e in r.audit]
    assert stages == ["ingest", "asr", "diarize", "redact", "emit", "store", "complete"]
    assert stages.index("redact") < stages.index("emit") < stages.index("store")
    assert redaction_precedes_emission(r) is True


def test_the_ordering_check_reads_the_artifact_not_the_source():
    """An auditor with a stored transcript and no repo access must be able to run it."""
    forged = PipelineResult(
        segments=(),
        audit=(AuditEvent("emit", {}), AuditEvent("redact", {})),
        redaction=None,
        redaction_applied=True,
    )
    assert redaction_precedes_emission(forged) is False
    missing = PipelineResult(segments=(), audit=(AuditEvent("emit", {}),), redaction=None)
    assert redaction_precedes_emission(missing) is False


def test_audit_records_what_redaction_caught_without_recording_what_it_was(result):
    redact_event = next(e for e in result.audit if e.stage == "redact")
    assert redact_event.detail["findings"] == result.redaction.total
    assert redact_event.detail["counts"] == result.redaction.counts
    assert len(redact_event.detail["redacted_sha256"]) == 64
    blob = json.dumps(redact_event.detail)
    for secret in FIXTURE_SECRETS:
        assert secret not in blob


def test_caller_metadata_values_are_not_copied_into_the_audit_log():
    """Caller metadata routinely carries participant names and numbers, and it does NOT go
    through the transcript redactor — so only its keys are recorded."""
    r = default_pipeline().run(metadata={"agent_phone": "07700 900482", "call_id": "x1"})
    ingest = next(e for e in r.audit if e.stage == "ingest")
    assert ingest.detail["metadata_keys"] == ["agent_phone", "call_id"]
    assert "07700 900482" not in json.dumps(r.to_dict())


def test_a_failing_sink_does_not_take_the_pipeline_down():
    def bad(_segments):
        raise RuntimeError("downstream is having a day")

    pipe = VoicePipeline(asr=FixtureAdapter(), emit_sinks=[bad])
    r = pipe.run()
    emit = next(e for e in r.audit if e.stage == "emit")
    assert emit.detail["sink_errors"] and "downstream is having a day" in emit.detail["sink_errors"][0]
    assert r.redaction_applied is True


# ---------------------------------------------------------------------------------------
# Storage refuses unredacted writes
# ---------------------------------------------------------------------------------------


def test_store_refuses_a_result_that_was_not_redacted(tmp_path):
    store = FilesystemTranscriptStore(tmp_path)
    unredacted = PipelineResult(segments=(), audit=(), redaction=None, redaction_applied=False)
    with pytest.raises(UnredactedWriteRefused):
        store.put(unredacted)
    assert list(tmp_path.glob("*.json")) == []


def test_in_memory_store_refuses_too():
    store = InMemoryTranscriptStore()
    with pytest.raises(UnredactedWriteRefused):
        store.put(PipelineResult(segments=(), audit=(), redaction=None, redaction_applied=False))
    assert store.items == {}


def test_stored_artifact_holds_redacted_text_and_the_audit_log(tmp_path):
    store = FilesystemTranscriptStore(tmp_path)
    pipe = VoicePipeline(asr=FixtureAdapter(), diarizer=HeuristicDiarizer(), store=store)
    pipe.run(metadata={"call_id": "stored-1"})
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["redaction"]["applied"] is True
    assert payload["audit"][3]["stage"] == "redact"
    blob = json.dumps(payload)
    for secret in FIXTURE_SECRETS:
        assert secret not in blob


# ---------------------------------------------------------------------------------------
# Policy plumbing
# ---------------------------------------------------------------------------------------


def test_policy_flows_from_the_pipeline_into_the_redactor():
    pipe = VoicePipeline(asr=FixtureAdapter(), policy=RedactionPolicy(redact_all_dates=True))
    assert any(d["type"] == "DATE" for d in pipe.redactor.active_detectors)


def test_pipeline_defaults_to_no_diarization_rather_than_a_guess():
    pipe = VoicePipeline(asr=FixtureAdapter())
    r = pipe.run()
    assert r.diarizer == "none"
    assert all(s.speaker is None for s in r.segments)
