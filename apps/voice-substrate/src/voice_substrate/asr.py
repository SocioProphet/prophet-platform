"""ASR adapters — (audio_path) -> list[TranscriptSegment].

The substrate/instrument separation this follows is the same one used in
needs-wants-instrument's substrate.py: the pipeline knows only the `AsrAdapter` contract,
so the engine underneath can be swapped (faster-whisper -> whisper.cpp -> a hosted API)
without touching diarization, redaction, or the service.

ENVIRONMENT REALITY, STATED UP FRONT
------------------------------------
No real ASR engine is installed on the machine this was written on. `faster_whisper`,
`whisper`, `vosk` and `pyannote.audio` all fail to import, and `ffmpeg` is not on PATH.
`FasterWhisperAdapter` below is real, correct code against the faster-whisper API — it has
simply never been executed here, and it says so rather than pretending. Anything that
needs to run today runs through `FixtureAdapter`, which is not ASR and is labelled as such
in every result it produces.

An adapter that cannot run fails LOUDLY at construction with the exact install command,
rather than degrading to empty segments. Silent degradation in a transcription substrate
means downstream analytics quietly score an empty transcript.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .types import TranscriptSegment

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class AdapterUnavailable(RuntimeError):
    """Raised when an adapter's dependency is missing. Always names the fix."""

    def __init__(self, adapter: str, reason: str, install: str) -> None:
        super().__init__(
            f"{adapter} is unavailable in this environment: {reason}. "
            f"To enable it: {install}"
        )
        self.adapter = adapter
        self.reason = reason
        self.install = install


@dataclass(frozen=True)
class Availability:
    available: bool
    reason: str
    install: str = ""


@runtime_checkable
class AsrAdapter(Protocol):
    """audio_path -> ordered transcript segments."""

    name: str

    def transcribe(self, audio_path: str | Path) -> list[TranscriptSegment]: ...

    @classmethod
    def availability(cls) -> Availability: ...


# ---------------------------------------------------------------------------------------
# faster-whisper
# ---------------------------------------------------------------------------------------

_FASTER_WHISPER_INSTALL = "pip install faster-whisper==1.0.3 (and install ffmpeg: brew install ffmpeg)"


class FasterWhisperAdapter:
    """CTranslate2 Whisper via faster-whisper.

    NOT EXECUTED IN THIS ENVIRONMENT. The dependency is absent here (see module docstring),
    so this code path is unverified end-to-end. It is written against the documented
    faster-whisper 1.x API — `WhisperModel(...).transcribe(path, ...)` returning a
    (segments generator, info) pair with `.start`, `.end`, `.text`, `.avg_logprob` on each
    segment — and the import is deferred to call time so importing this module never
    requires the dep.

    No WER figure is claimed for this or any other adapter: there is no evaluation set in
    this estate to measure one against.
    """

    name = "faster_whisper"

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
        beam_size: int = 5,
        language: str | None = None,
        vad_filter: bool = True,
    ) -> None:
        avail = self.availability()
        if not avail.available:
            raise AdapterUnavailable(self.name, avail.reason, avail.install)
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.language = language
        self.vad_filter = vad_filter
        self._model = None

    @classmethod
    def availability(cls) -> Availability:
        try:
            spec = importlib.util.find_spec("faster_whisper")
        except (ImportError, ModuleNotFoundError, ValueError):
            spec = None
        if spec is None:
            return Availability(
                False,
                "python module 'faster_whisper' is not importable",
                _FASTER_WHISPER_INSTALL,
            )
        if shutil.which("ffmpeg") is None:
            # faster-whisper decodes via PyAV rather than shelling out to ffmpeg, but the
            # FFmpeg libraries still have to be present; flag it rather than fail at
            # transcribe time with an opaque decoder error.
            return Availability(
                False,
                "faster_whisper is importable but ffmpeg is not on PATH (audio decoding will fail)",
                "brew install ffmpeg",
            )
        return Availability(True, "faster_whisper + ffmpeg present")

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # noqa: PLC0415  (deferred by design)

            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def transcribe(self, audio_path: str | Path) -> list[TranscriptSegment]:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"audio file not found: {path}")
        model = self._load()
        segments, _info = model.transcribe(
            str(path),
            beam_size=self.beam_size,
            language=self.language,
            vad_filter=self.vad_filter,
        )
        import math  # noqa: PLC0415

        out: list[TranscriptSegment] = []
        for s in segments:  # generator — consuming it is what performs the work
            logprob = getattr(s, "avg_logprob", None)
            out.append(
                TranscriptSegment(
                    start=float(s.start),
                    end=float(s.end),
                    text=s.text.strip(),
                    speaker=None,  # whisper does not diarize; see diarization.py
                    confidence=(math.exp(logprob) if logprob is not None else None),
                )
            )
        return out


# ---------------------------------------------------------------------------------------
# Fixture replay
# ---------------------------------------------------------------------------------------


class FixtureAdapter:
    """Replays a canned transcript. THIS IS NOT ASR — no audio is decoded or recognised.

    It exists so the rest of the substrate (diarization, redaction, the audit trail, the
    HTTP surface) is exercisable and testable in an environment with no speech tooling. Its
    `name` is prefixed "fixture:" and `PipelineResult.provenance.real_asr` is False for any
    run that used it, so a fixture result can never be mistaken for a transcription in an
    audit log or a downstream store.
    """

    def __init__(
        self,
        segments: list[TranscriptSegment] | None = None,
        fixture: str = "pii_sampler",
    ) -> None:
        self.fixture = fixture
        self.name = f"fixture:{fixture}"
        self._segments = segments if segments is not None else self._load_fixture(fixture)

    @staticmethod
    def _load_fixture(fixture: str) -> list[TranscriptSegment]:
        path = FIXTURE_DIR / f"{fixture}.json"
        if not path.exists():
            available = sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))
            raise FileNotFoundError(
                f"no such fixture transcript: {fixture!r} (available: {available})"
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [
            TranscriptSegment(
                start=float(s["start"]),
                end=float(s["end"]),
                text=s["text"],
                speaker=s.get("speaker"),
                confidence=s.get("confidence"),
            )
            for s in raw["segments"]
        ]

    @classmethod
    def availability(cls) -> Availability:
        return Availability(True, "canned transcript replay — NOT real speech recognition")

    def transcribe(self, audio_path: str | Path | None = None) -> list[TranscriptSegment]:
        # audio_path is accepted and deliberately ignored: the signature matches AsrAdapter
        # so the pipeline is identical, but no audio is read. Nothing about the returned
        # segments depends on the file.
        return list(self._segments)


ASR_ADAPTERS: dict[str, type] = {
    "faster_whisper": FasterWhisperAdapter,
    "fixture": FixtureAdapter,
}


def asr_availability() -> dict[str, dict[str, object]]:
    """Per-adapter availability in THIS process — what /healthz reports."""
    out: dict[str, dict[str, object]] = {}
    for key, cls in ASR_ADAPTERS.items():
        a = cls.availability()
        out[key] = {
            "available": a.available,
            "reason": a.reason,
            "install": a.install,
            "real_asr": key != "fixture",
        }
    return out
