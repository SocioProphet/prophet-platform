"""voice-substrate HTTP service — FastAPI.

Endpoints
  GET  /healthz    which adapters are actually available IN THIS PROCESS, and why not
  GET  /policy     redaction classes covered, classes NOT covered, environment honesty
  POST /transcribe audio -> segments -> diarize -> redact -> result (+ audit log)
  POST /redact     redaction only, over supplied text (no audio, no ASR needed)
  POST /transcribe/upload   same as /transcribe but multipart — registered only when
                            python-multipart is installed; /healthz says whether it is

DESIGN NOTE ON `asr: "auto"`
----------------------------
"auto" resolves to a real ASR engine or it 503s naming the install command. It does NOT
fall back to the fixture adapter. A substrate that silently answers a transcription request
with canned text is worse than one that refuses: the caller gets a plausible transcript and
no signal that nothing was transcribed. Fixture replay is available, but only when the
caller asks for it by name.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import __version__
from .asr import ASR_ADAPTERS, AdapterUnavailable, FasterWhisperAdapter, FixtureAdapter, asr_availability
from .diarization import DIARIZERS, HeuristicDiarizer, NullDiarizer, PyannoteAdapter, diarization_availability
from .pipeline import STAGES, VoicePipeline, redaction_precedes_emission
from .redaction import (
    COVERED,
    NOT_COVERED,
    POLICY_VERSION,
    Redactor,
    RedactionPolicy,
    person_ner_available,
)
from .storage import FilesystemTranscriptStore, InMemoryTranscriptStore

app = FastAPI(title="voice-substrate", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STORE_ROOT = os.environ.get("VOICE_SUBSTRATE_STORE")
STORE = FilesystemTranscriptStore(STORE_ROOT) if STORE_ROOT else InMemoryTranscriptStore()
UPLOAD_ENABLED = importlib.util.find_spec("multipart") is not None

ENVIRONMENT_NOTE = (
    "No real ASR engine is installed in this environment. faster_whisper, whisper, vosk "
    "and pyannote.audio are all unimportable and ffmpeg is not on PATH, so the only "
    "end-to-end path that runs today is FixtureAdapter (canned transcript replay, NOT "
    "speech recognition) plus the redactor, which is pure Python and always runs. "
    "Install faster-whisper + ffmpeg to enable real transcription and pyannote.audio to "
    "enable real diarization; /healthz reports live status per adapter."
)
NO_METRICS_NOTE = (
    "No WER, DER, precision or recall figure is published by this service. There is no "
    "labelled evaluation set for speech or PII anywhere in this estate, so any such "
    "number would be fabricated. The structural validators (Luhn, IBAN mod-97, SSN "
    "issuing ranges) are exact by construction; nothing else here is measured."
)


class TranscribeReq(BaseModel):
    audio_path: str | None = Field(
        None, description="server-side path to the audio file; required for real ASR"
    )
    asr: str = Field("auto", description="auto | faster_whisper | fixture")
    diarizer: str = Field("heuristic", description="heuristic | pyannote | none")
    fixture: str = Field("pii_sampler", description="fixture name when asr=fixture")
    redact_all_dates: bool = False
    enable_person_names: bool = False
    store: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RedactReq(BaseModel):
    text: str
    redact_all_dates: bool = False
    enable_person_names: bool = False


def _build_policy(req: TranscribeReq | RedactReq) -> RedactionPolicy:
    return RedactionPolicy(
        redact_all_dates=req.redact_all_dates,
        enable_person_names=req.enable_person_names,
    )


def _resolve_asr(req: TranscribeReq):
    choice = req.asr
    if choice == "auto":
        avail = FasterWhisperAdapter.availability()
        if not avail.available:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "no real ASR adapter is available in this environment",
                    "reason": avail.reason,
                    "install": avail.install,
                    "hint": "set asr='fixture' to exercise the pipeline with a canned "
                            "transcript — the result is explicitly labelled NOT real ASR",
                },
            )
        return FasterWhisperAdapter()
    if choice == "fixture":
        try:
            return FixtureAdapter(fixture=req.fixture)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if choice not in ASR_ADAPTERS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown asr adapter {choice!r}; known: {sorted(ASR_ADAPTERS)}",
        )
    try:
        return ASR_ADAPTERS[choice]()
    except AdapterUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": str(exc), "adapter": exc.adapter, "install": exc.install},
        ) from exc


def _resolve_diarizer(req: TranscribeReq):
    choice = req.diarizer
    if choice == "heuristic":
        return HeuristicDiarizer()
    if choice == "none":
        return NullDiarizer()
    if choice == "pyannote":
        try:
            return PyannoteAdapter()
        except AdapterUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail={"error": str(exc), "adapter": exc.adapter, "install": exc.install},
            ) from exc
    raise HTTPException(
        status_code=400,
        detail=f"unknown diarizer {choice!r}; known: {sorted(DIARIZERS)}",
    )


def _run(req: TranscribeReq) -> dict[str, Any]:
    asr = _resolve_asr(req)
    diarizer = _resolve_diarizer(req)
    if req.enable_person_names:
        ok, reason = person_ner_available()
        if not ok:
            raise HTTPException(
                status_code=503,
                detail={"error": "person-name redaction requested but unavailable", "reason": reason},
            )
    pipeline = VoicePipeline(
        asr=asr,
        diarizer=diarizer,
        policy=_build_policy(req),
        store=STORE if req.store else None,
    )
    if req.audio_path and not Path(req.audio_path).exists() and req.asr != "fixture":
        raise HTTPException(status_code=400, detail=f"audio file not found: {req.audio_path}")
    try:
        result = pipeline.run(audio_path=req.audio_path, metadata=req.metadata)
    except AdapterUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": str(exc), "adapter": exc.adapter, "install": exc.install},
        ) from exc
    payload = result.to_dict()
    payload["guarantees"] = {
        "redaction_ran_before_emission": redaction_precedes_emission(result),
        "stages": list(STAGES),
        "checked_from": "the audit log in this response, not from source inspection",
    }
    payload["no_accuracy_claim"] = NO_METRICS_NOTE
    return payload


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    """Liveness AND capability honesty: an operator sees here that ASR is unavailable,
    rather than discovering it from an opaque error on the first real request."""
    asr = asr_availability()
    diar = diarization_availability()
    ner_ok, ner_reason = person_ner_available()
    real_asr = [k for k, v in asr.items() if v["available"] and v["real_asr"]]
    real_diar = [k for k, v in diar.items() if v["available"] and v["is_speaker_identification"]]
    return {
        "ok": True,
        "service": "voice-substrate",
        "version": __version__,
        "asr_adapters": asr,
        "diarization_adapters": diar,
        "redaction": {
            "available": True,
            "reason": "pure python, no third-party dependency — always runs",
            "policy_version": POLICY_VERSION,
            "person_name_ner": {"available": ner_ok, "reason": ner_reason, "opt_in": True},
        },
        "capability_summary": {
            "real_asr_available": bool(real_asr),
            "real_asr_adapters": real_asr,
            "real_speaker_identification_available": bool(real_diar),
            "real_speaker_identification_adapters": real_diar,
            "upload_endpoint_enabled": UPLOAD_ENABLED,
            "degraded": not real_asr,
            "degraded_reason": None if real_asr else ENVIRONMENT_NOTE,
        },
    }


@app.get("/policy")
def policy() -> dict[str, Any]:
    r = Redactor()
    return {
        "policy_version": POLICY_VERSION,
        "pipeline_stages": list(STAGES),
        "ordering_guarantee": (
            "redaction runs before emission, storage or any downstream consumer sees the "
            "text; enforced by type separation (raw TranscriptSegment vs RedactedSegment) "
            "and recorded in the per-request audit log"
        ),
        "manifest_rule": (
            "the redaction manifest records type, detector and character span only. "
            "Removed values are never echoed — not in responses, not in logs, not in the "
            "stored artifact."
        ),
        "redaction_covered": list(COVERED),
        "redaction_not_covered": list(NOT_COVERED),
        "active_detectors": r.active_detectors,
        "environment": ENVIRONMENT_NOTE,
        "accuracy": NO_METRICS_NOTE,
        "diarization_honesty": (
            "the default diarizer is HeuristicDiarizer: silence-gap turn alternation over "
            "ASR timings. It never opens the audio and performs no voice modelling, so it "
            "is NOT speaker identification. Labels are positional and not stable "
            "identities across a transcript. Real speaker identification requires the "
            "pyannote adapter, which is not installed here."
        ),
    }


@app.post("/transcribe")
def transcribe(req: TranscribeReq) -> dict[str, Any]:
    return _run(req)


@app.post("/redact")
def redact(req: RedactReq) -> dict[str, Any]:
    """Redaction over supplied text. Needs no audio and no ASR dependency, so this
    endpoint works fully in every environment the service can boot in."""
    if req.enable_person_names:
        ok, reason = person_ner_available()
        if not ok:
            raise HTTPException(
                status_code=503,
                detail={"error": "person-name redaction requested but unavailable", "reason": reason},
            )
    r = Redactor(_build_policy(req))
    res = r.redact(req.text)
    return {
        "text": res.text,
        "policy_version": res.policy_version,
        "redacted_sha256": res.redacted_sha256,
        "counts": dict(res.counts),
        "total_findings": res.total,
        "manifest": [
            {"type": f.type, "detector": f.detector, "start": f.start, "end": f.end, "length": f.length}
            for f in res.findings
        ],
        "manifest_rule": "type + span only; removed values are never echoed",
    }


if UPLOAD_ENABLED:  # pragma: no cover - depends on python-multipart being installed
    import tempfile

    from fastapi import File, Form, UploadFile

    @app.post("/transcribe/upload")
    async def transcribe_upload(
        audio: UploadFile = File(...),
        asr: str = Form("auto"),
        diarizer: str = Form("heuristic"),
        fixture: str = Form("pii_sampler"),
        store: bool = Form(False),
        metadata: str = Form("{}"),
    ) -> dict[str, Any]:
        suffix = Path(audio.filename or "upload").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        try:
            meta = json.loads(metadata or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"metadata is not valid JSON: {exc}") from exc
        try:
            return _run(TranscribeReq(
                audio_path=tmp_path, asr=asr, diarizer=diarizer, fixture=fixture,
                store=store, metadata=meta,
            ))
        finally:
            os.unlink(tmp_path)
