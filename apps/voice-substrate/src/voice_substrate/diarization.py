"""Diarization adapters — assign speaker labels to transcript segments.

Same substrate/instrument split as asr.py: the pipeline depends on the
`DiarizationAdapter` contract only.

WHAT IS AND IS NOT DIARIZATION
------------------------------
Real diarization clusters *voice* — it embeds speech, groups embeddings, and answers "was
this the same person?". `PyannoteAdapter` does that. It is not installed here
(`pyannote.audio` fails to import), so it raises with the install command rather than
pretending.

`HeuristicDiarizer` does NOT do that. It never looks at the audio at all. It splits on
silence gaps and alternates labels, which is a turn-segmentation heuristic that happens to
produce speaker-shaped labels. It is useful — in a scheduled two-party call it is right
more often than a single-speaker assumption — and it is honest about being a proxy. Its
failure modes are enumerated in the class docstring and echoed in every result it labels,
because a downstream consumer that mistakes it for speaker identification would attribute
utterances to the wrong person with full confidence.
"""
from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path
from typing import Protocol, runtime_checkable

from .asr import AdapterUnavailable, Availability
from .types import TranscriptSegment


@runtime_checkable
class DiarizationAdapter(Protocol):
    """segments (+ optional audio) -> segments with `speaker` populated."""

    name: str
    is_speaker_identification: bool

    def assign(
        self, segments: list[TranscriptSegment], audio_path: str | Path | None = None
    ) -> list[TranscriptSegment]: ...

    @classmethod
    def availability(cls) -> Availability: ...


def _spec_exists(name: str) -> bool:
    """importlib.util.find_spec raises (rather than returning None) for a dotted name whose
    PARENT package is missing, which is exactly the case here — so probing 'pyannote.audio'
    on a machine without pyannote would crash /healthz. Guard it."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


_PYANNOTE_INSTALL = (
    "pip install 'pyannote.audio==3.3.2' and accept the model terms for "
    "pyannote/speaker-diarization-3.1 on huggingface.co, then set HUGGINGFACE_TOKEN"
)


class PyannoteAdapter:
    """Real speaker diarization via pyannote.audio's speaker-diarization-3.1 pipeline.

    NOT EXECUTED IN THIS ENVIRONMENT — `pyannote.audio` is not importable here, and the
    pipeline additionally requires a Hugging Face token and acceptance of the model's
    gated terms. The code below is written against the documented pyannote 3.x API
    (`Pipeline.from_pretrained(...)` then `itertracks(yield_label=True)` over the returned
    annotation) with the import deferred to call time.

    No DER (diarization error rate) is claimed. There is no annotated evaluation set in
    this estate, and quoting the paper's number as if it were ours would be a fabrication.
    """

    name = "pyannote"
    is_speaker_identification = True

    def __init__(
        self,
        model: str = "pyannote/speaker-diarization-3.1",
        auth_token: str | None = None,
        num_speakers: int | None = None,
    ) -> None:
        avail = self.availability()
        if not avail.available:
            raise AdapterUnavailable(self.name, avail.reason, avail.install)
        self.model = model
        self.auth_token = auth_token
        self.num_speakers = num_speakers
        self._pipeline = None

    @classmethod
    def availability(cls) -> Availability:
        if not _spec_exists("pyannote.audio"):
            return Availability(
                False, "python module 'pyannote.audio' is not importable", _PYANNOTE_INSTALL
            )
        if not _spec_exists("torch"):
            return Availability(
                False, "pyannote.audio present but torch is not importable", "pip install torch"
            )
        return Availability(True, "pyannote.audio + torch present")

    def _load(self):
        if self._pipeline is None:
            from pyannote.audio import Pipeline  # noqa: PLC0415  (deferred by design)

            self._pipeline = Pipeline.from_pretrained(
                self.model, use_auth_token=self.auth_token
            )
        return self._pipeline

    def assign(
        self, segments: list[TranscriptSegment], audio_path: str | Path | None = None
    ) -> list[TranscriptSegment]:
        if audio_path is None:
            raise ValueError(
                "PyannoteAdapter needs the audio file: it clusters voice embeddings, it "
                "cannot infer speakers from transcript text alone"
            )
        pipeline = self._load()
        kwargs = {"num_speakers": self.num_speakers} if self.num_speakers else {}
        annotation = pipeline(str(audio_path), **kwargs)
        turns = [
            (turn.start, turn.end, label)
            for turn, _track, label in annotation.itertracks(yield_label=True)
        ]
        out: list[TranscriptSegment] = []
        for seg in segments:
            # attribute each ASR segment to the diarization turn it overlaps most
            best_label, best_overlap = None, 0.0
            for t_start, t_end, label in turns:
                overlap = min(seg.end, t_end) - max(seg.start, t_start)
                if overlap > best_overlap:
                    best_label, best_overlap = label, overlap
            out.append(replace(seg, speaker=best_label))
        return out


class HeuristicDiarizer:
    """Turn-alternation on silence gaps. THIS IS NOT SPEAKER IDENTIFICATION.

    Method: walk the segments in time order; when the gap to the previous segment exceeds
    `gap_seconds`, advance to the next speaker label, cycling through `num_speakers`
    labels. The audio is never opened; no voice characteristic is measured anywhere.

    Why it is here: in a scheduled two-party conversation, turn boundaries correlate with
    pauses often enough that this beats labelling everything as one speaker, and it lets
    the rest of the substrate be built and tested without a diarization dependency.

    NAMED FAILURE MODES — all of these are expected, not edge cases:
      * A speaker who pauses mid-thought is relabelled as a different speaker. Long
        monologues with natural pauses get shredded into fake turns.
      * A speaker change with no pause (interruption, overlap, rapid back-and-forth) is
        missed entirely; both speakers land under one label.
      * Labels are POSITIONAL, not identities. `speaker_0` early in the transcript and
        `speaker_0` later are not guaranteed to be the same human — there is no
        re-identification, because there is no voice model. Do not aggregate per-speaker
        statistics across a transcript on the strength of these labels.
      * The speaker count is assumed, not detected. With three participants and
        num_speakers=2 the labels are meaningless.
      * Overlapping speech is not representable at all: one segment gets one label.

    `is_speaker_identification` is False, and the pipeline surfaces that flag plus a
    warning on every result, so a consumer has to actively ignore the disclaimer to
    misuse it.
    """

    name = "heuristic_turn_alternation"
    is_speaker_identification = False
    method = "silence-gap turn alternation over ASR segment timings (no audio, no voice model)"

    def __init__(self, gap_seconds: float = 0.75, num_speakers: int = 2) -> None:
        if gap_seconds <= 0:
            raise ValueError("gap_seconds must be positive")
        if num_speakers < 1:
            raise ValueError("num_speakers must be >= 1")
        self.gap_seconds = gap_seconds
        self.num_speakers = num_speakers

    @classmethod
    def availability(cls) -> Availability:
        return Availability(
            True,
            "pure-python heuristic — always available, and NOT speaker identification",
        )

    def assign(
        self, segments: list[TranscriptSegment], audio_path: str | Path | None = None
    ) -> list[TranscriptSegment]:
        ordered = sorted(range(len(segments)), key=lambda i: segments[i].start)
        speaker_idx = 0
        out: list[TranscriptSegment | None] = [None] * len(segments)
        prev_end: float | None = None
        for pos, i in enumerate(ordered):
            seg = segments[i]
            if prev_end is not None and (seg.start - prev_end) > self.gap_seconds:
                speaker_idx = (speaker_idx + 1) % self.num_speakers
            out[i] = replace(seg, speaker=f"speaker_{speaker_idx}")
            prev_end = max(prev_end or seg.end, seg.end)
        return [s for s in out if s is not None]

    def warnings(self) -> list[str]:
        return [
            "speaker labels come from HeuristicDiarizer: silence-gap turn alternation, "
            "NOT speaker identification. Labels are positional and are not stable "
            "identities across the transcript.",
            f"speaker count was assumed ({self.num_speakers}), not detected from audio.",
        ]


class NullDiarizer:
    """Assigns no speakers. The honest option when nothing is known about the audio."""

    name = "none"
    is_speaker_identification = False
    method = "no speaker attribution"

    @classmethod
    def availability(cls) -> Availability:
        return Availability(True, "no-op")

    def assign(
        self, segments: list[TranscriptSegment], audio_path: str | Path | None = None
    ) -> list[TranscriptSegment]:
        return list(segments)

    def warnings(self) -> list[str]:
        return ["no diarization was performed; every segment is unattributed"]


DIARIZERS: dict[str, type] = {
    "pyannote": PyannoteAdapter,
    "heuristic": HeuristicDiarizer,
    "none": NullDiarizer,
}


def diarization_availability() -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for key, cls in DIARIZERS.items():
        a = cls.availability()
        out[key] = {
            "available": a.available,
            "reason": a.reason,
            "install": a.install,
            "is_speaker_identification": cls.is_speaker_identification,
        }
    return out
