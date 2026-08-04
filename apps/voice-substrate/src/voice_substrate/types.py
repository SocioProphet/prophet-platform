"""Core data types for the voice substrate.

Two segment types exist on purpose, and the distinction is load-bearing:

  TranscriptSegment  — RAW ASR output. May contain anything the speaker said, including
                       PII. Never leaves the pipeline; never serialized to a response;
                       never written to storage.
  RedactedSegment    — post-redaction. This is the ONLY segment type any downstream
                       consumer, HTTP response, or store is allowed to see.

Keeping them as separate types means "did redaction run?" is answerable by reading a
type signature rather than by trusting a comment. `PipelineResult` can only hold
RedactedSegment, so a pipeline that skipped redaction cannot construct one.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranscriptSegment:
    """One ASR segment. RAW — may contain PII. Internal to the pipeline only."""

    start: float
    end: float
    text: str
    speaker: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"segment end ({self.end}) precedes start ({self.start})")

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class RedactionFinding:
    """One redacted span.

    Deliberately carries NO copy of the removed value. The estate rule is that scanners
    never echo their matches, so the manifest records *what class was found and where*,
    never *what it was*. `length` is the character length of the removed span in the
    pre-redaction text; it is metadata about the removal, not the value.
    """

    type: str
    detector: str
    start: int
    end: int
    length: int
    segment_index: int | None = None


@dataclass(frozen=True)
class RedactionResult:
    text: str
    findings: tuple[RedactionFinding, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)
    redacted_sha256: str = ""
    policy_version: str = ""

    @property
    def total(self) -> int:
        return len(self.findings)


@dataclass(frozen=True)
class RedactedSegment:
    """A segment that has provably been through the redactor."""

    start: float
    end: float
    text: str
    speaker: str | None = None
    confidence: float | None = None
    redactions: tuple[RedactionFinding, ...] = ()


@dataclass(frozen=True)
class AuditEvent:
    """One ordered pipeline-stage record. The audit log is what makes the redaction
    guarantee checkable after the fact instead of merely asserted."""

    stage: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineResult:
    segments: tuple[RedactedSegment, ...]
    audit: tuple[AuditEvent, ...]
    redaction: RedactionResult | None
    asr_adapter: str = ""
    diarizer: str = ""
    redaction_applied: bool = False
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": [asdict(s) for s in self.segments],
            "audit": [asdict(a) for a in self.audit],
            "redaction": {
                "applied": self.redaction_applied,
                "policy_version": self.redaction.policy_version if self.redaction else None,
                "counts": dict(self.redaction.counts) if self.redaction else {},
                "total_findings": self.redaction.total if self.redaction else 0,
                "manifest": [asdict(f) for f in self.redaction.findings] if self.redaction else [],
                "note": "manifest records class + span only; removed values are never echoed",
            },
            "provenance": {
                "asr_adapter": self.asr_adapter,
                "diarizer": self.diarizer,
                "real_asr": not self.asr_adapter.startswith("fixture"),
            },
            "warnings": list(self.warnings),
        }
