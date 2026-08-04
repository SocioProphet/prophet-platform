"""The voice pipeline: ingest -> ASR -> diarize -> REDACT -> emit (-> store).

This is framework §10.3 step 1 as executable code. The ordering is the point. Redaction is
not a filter applied to output; it is a stage that raw text cannot get past.

HOW THE ORDERING IS ENFORCED (rather than merely intended)
----------------------------------------------------------
1. Type separation. `TranscriptSegment` (raw) is a different type from `RedactedSegment`,
   and `PipelineResult` can only hold the latter. A pipeline that skipped redaction has
   nothing to construct a result from.
2. Local scope. The raw segment list is a local inside `run()`. It is never assigned to
   the result, never handed to a sink, and never passed to the store.
3. Sinks run after. Downstream consumers register via `emit_sinks` and are invoked in the
   emit stage, which is entered only after the redact stage has returned.
4. The audit log records every stage in order, with the redaction manifest summary. So the
   guarantee is *checkable* from the artifact — `redaction_precedes_emission()` below reads
   the emitted audit log rather than trusting this docstring.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .asr import AsrAdapter, FixtureAdapter
from .diarization import DiarizationAdapter, HeuristicDiarizer, NullDiarizer
from .redaction import DEFAULT_POLICY, Redactor, RedactionPolicy
from .storage import TranscriptStore
from .types import AuditEvent, PipelineResult, RedactedSegment, TranscriptSegment

STAGES = ("ingest", "asr", "diarize", "redact", "emit", "store")

EmitSink = Callable[[Sequence[RedactedSegment]], None]


@dataclass
class VoicePipeline:
    asr: AsrAdapter
    diarizer: DiarizationAdapter | None = None
    policy: RedactionPolicy = DEFAULT_POLICY
    store: TranscriptStore | None = None
    emit_sinks: list[EmitSink] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.diarizer is None:
            self.diarizer = NullDiarizer()
        self.redactor = Redactor(self.policy)

    def run(
        self,
        audio_path: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineResult:
        audit: list[AuditEvent] = []
        warnings: list[str] = []
        t0 = time.perf_counter()

        # -- 1. ingest ------------------------------------------------------------------
        meta = dict(metadata or {})
        size = None
        if audio_path is not None:
            p = Path(audio_path)
            size = p.stat().st_size if p.exists() else None
        audit.append(AuditEvent("ingest", {
            "audio_path_supplied": audio_path is not None,
            "audio_bytes": size,
            # metadata KEYS only. Caller metadata is untrusted for PII: it routinely
            # carries participant names and phone numbers, and it does not go through the
            # transcript redactor, so values are not copied into the audit log.
            "metadata_keys": sorted(meta.keys()),
        }))

        # -- 2. ASR ---------------------------------------------------------------------
        raw_segments: list[TranscriptSegment] = self.asr.transcribe(audio_path)
        real_asr = not getattr(self.asr, "name", "").startswith("fixture")
        if not real_asr:
            warnings.append(
                "NO REAL ASR: this transcript came from a fixture replay adapter, not from "
                "speech recognition. Do not treat it as a transcription of the submitted audio."
            )
        audit.append(AuditEvent("asr", {
            "adapter": self.asr.name,
            "real_asr": real_asr,
            "segments": len(raw_segments),
            "audio_seconds": round(max((s.end for s in raw_segments), default=0.0), 3),
        }))

        # -- 3. diarize -----------------------------------------------------------------
        diarizer = self.diarizer
        assert diarizer is not None
        raw_segments = diarizer.assign(raw_segments, audio_path)
        is_sid = getattr(diarizer, "is_speaker_identification", False)
        if not is_sid and getattr(diarizer, "name", "") != "none":
            warnings.extend(getattr(diarizer, "warnings", lambda: [])())
        audit.append(AuditEvent("diarize", {
            "adapter": diarizer.name,
            "is_speaker_identification": is_sid,
            "method": getattr(diarizer, "method", ""),
            "speakers_labelled": sorted({s.speaker for s in raw_segments if s.speaker}),
        }))

        # -- 4. REDACT (nothing downstream has seen the text at this point) --------------
        redacted_segments, redaction = self.redactor.redact_segments(raw_segments)
        audit.append(AuditEvent("redact", {
            "policy_version": redaction.policy_version,
            "detectors_active": len(self.redactor.detectors),
            "types_active": self.redactor.active_types,
            "findings": redaction.total,
            "counts": dict(redaction.counts),
            "redacted_sha256": redaction.redacted_sha256,
            "note": "manifest carries type + span only; removed values are never recorded",
        }))
        # Raw text is dropped here. From this line on, only `redacted_segments` exists.
        del raw_segments

        result = PipelineResult(
            segments=tuple(redacted_segments),
            audit=(),  # filled below once the remaining stages have run
            redaction=redaction,
            asr_adapter=self.asr.name,
            diarizer=diarizer.name,
            redaction_applied=True,
            warnings=tuple(warnings),
        )

        # -- 5. emit --------------------------------------------------------------------
        sink_errors: list[str] = []
        for sink in self.emit_sinks:
            try:
                sink(result.segments)  # redacted segments only, by construction
            except Exception as exc:  # a bad sink must not take the pipeline down
                sink_errors.append(f"{getattr(sink, '__name__', repr(sink))}: {exc}")
        audit.append(AuditEvent("emit", {
            "sinks": len(self.emit_sinks),
            "sink_errors": sink_errors,
            "emitted_type": RedactedSegment.__name__,
        }))

        # -- 6. store -------------------------------------------------------------------
        transcript_id = None
        if self.store is not None:
            interim = PipelineResult(
                segments=result.segments,
                audit=tuple(audit),
                redaction=redaction,
                asr_adapter=result.asr_adapter,
                diarizer=result.diarizer,
                redaction_applied=True,
                warnings=result.warnings,
            )
            transcript_id = self.store.put(interim, metadata=meta)
            audit.append(AuditEvent("store", {"transcript_id": transcript_id}))

        audit.append(AuditEvent("complete", {
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "transcript_id": transcript_id,
        }))

        return PipelineResult(
            segments=result.segments,
            audit=tuple(audit),
            redaction=redaction,
            asr_adapter=result.asr_adapter,
            diarizer=result.diarizer,
            redaction_applied=True,
            warnings=result.warnings,
        )


def redaction_precedes_emission(result: PipelineResult) -> bool:
    """Read the emitted audit log and confirm redact ran before emit/store.

    Deliberately implemented as an inspection of the artifact rather than of the code, so
    it can be run by an auditor against a stored transcript with no access to this
    repository.
    """
    stages = [e.stage for e in result.audit]
    if "redact" not in stages:
        return False
    redact_at = stages.index("redact")
    for downstream in ("emit", "store"):
        if downstream in stages and stages.index(downstream) < redact_at:
            return False
    return True


def default_pipeline(
    *,
    fixture: str = "pii_sampler",
    policy: RedactionPolicy = DEFAULT_POLICY,
    store: TranscriptStore | None = None,
) -> VoicePipeline:
    """The pipeline that actually runs in an environment with no ASR installed: fixture
    replay + heuristic turn alternation + full redaction. Honest, not useful for real audio."""
    return VoicePipeline(
        asr=FixtureAdapter(fixture=fixture),
        diarizer=HeuristicDiarizer(),
        policy=policy,
        store=store,
    )
