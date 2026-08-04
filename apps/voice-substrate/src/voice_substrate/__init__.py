"""voice-substrate — ASR + diarization + redaction for prophet-platform.

Step 1 of the "Needs vs Wants" build order (§10.3): ingest audio + metadata, transcribe,
diarize, redact, store, audit. Nothing that infers about a speaker belongs in this package
— §10.2's trap is doing personality before you can do transcription, and this is the
transcription layer that has to exist first.

Read the module docstrings for the honesty position; the short version is in README.md and
on GET /policy: no real ASR engine is installed in this environment, so the only path that
runs end-to-end today is fixture replay plus the (real, dependency-free) redactor.
"""
from .asr import AdapterUnavailable, AsrAdapter, Availability, FasterWhisperAdapter, FixtureAdapter
from .diarization import DiarizationAdapter, HeuristicDiarizer, NullDiarizer, PyannoteAdapter
from .pipeline import VoicePipeline, default_pipeline, redaction_precedes_emission
from .redaction import (
    COVERED,
    NOT_COVERED,
    POLICY,
    POLICY_VERSION,
    Redactor,
    RedactionPolicy,
    iban_ok,
    luhn_ok,
    spoken_number_runs,
)
from .storage import FilesystemTranscriptStore, InMemoryTranscriptStore, UnredactedWriteRefused
from .types import (
    AuditEvent,
    PipelineResult,
    RedactedSegment,
    RedactionFinding,
    RedactionResult,
    TranscriptSegment,
)

__all__ = [
    "AdapterUnavailable", "AsrAdapter", "Availability", "AuditEvent", "COVERED",
    "DiarizationAdapter", "FasterWhisperAdapter", "FilesystemTranscriptStore",
    "FixtureAdapter", "HeuristicDiarizer", "InMemoryTranscriptStore", "NOT_COVERED",
    "NullDiarizer", "POLICY", "POLICY_VERSION", "PipelineResult", "PyannoteAdapter",
    "RedactedSegment", "RedactionFinding", "RedactionPolicy", "RedactionResult",
    "Redactor", "TranscriptSegment", "UnredactedWriteRefused", "VoicePipeline",
    "default_pipeline", "iban_ok", "luhn_ok", "redaction_precedes_emission",
    "spoken_number_runs",
]
__version__ = "0.1.0"
