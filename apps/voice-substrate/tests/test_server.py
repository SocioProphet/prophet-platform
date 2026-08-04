"""HTTP surface tests — capability honesty on /healthz, declared gaps on /policy.

The behaviour under test is as much about what the service REFUSES to do as what it does:
`asr="auto"` must 503 with an install command rather than quietly serving a fixture, and
/healthz must report the degradation before an operator discovers it from a confusing
runtime error.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from voice_substrate.asr import FasterWhisperAdapter
from voice_substrate.diarization import PyannoteAdapter
from voice_substrate.server import app

client = TestClient(app)

SECRETS = ["07700 900482", "j.harper@contoso.co.uk", "4539 1488 0343 6467",
           "123-45-6789", "221B Baker Street", "GB82 WEST 12345698765432"]


# ---------------------------------------------------------------------------------------
# /healthz — which adapters are ACTUALLY available in this process
# ---------------------------------------------------------------------------------------


def test_healthz_serves():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["service"] == "voice-substrate"


def test_healthz_reports_per_adapter_availability_with_a_reason():
    body = client.get("/healthz").json()
    for name, info in body["asr_adapters"].items():
        assert isinstance(info["available"], bool)
        assert info["reason"], f"{name} gives no reason"
        if not info["available"]:
            assert info["install"], f"{name} is unavailable but says nothing about the fix"
    for name, info in body["diarization_adapters"].items():
        assert info["reason"]


def test_healthz_summarises_degradation_honestly():
    body = client.get("/healthz").json()
    summary = body["capability_summary"]
    real = FasterWhisperAdapter.availability().available
    assert summary["real_asr_available"] is real
    assert summary["degraded"] is (not real)
    if not real:
        assert "No real ASR engine is installed" in summary["degraded_reason"]
        assert "faster-whisper" in summary["degraded_reason"]


def test_healthz_does_not_call_the_fixture_adapter_real_asr():
    body = client.get("/healthz").json()
    assert body["asr_adapters"]["fixture"]["real_asr"] is False
    assert "fixture" not in body["capability_summary"]["real_asr_adapters"]


def test_healthz_reports_redaction_as_always_available():
    body = client.get("/healthz").json()
    assert body["redaction"]["available"] is True
    assert "no third-party dependency" in body["redaction"]["reason"]


def test_healthz_survives_a_missing_parent_package():
    """pyannote.audio's parent package is absent here; probing it must not 500."""
    assert client.get("/healthz").status_code == 200


# ---------------------------------------------------------------------------------------
# /policy — covered AND not covered
# ---------------------------------------------------------------------------------------


def test_policy_lists_covered_and_not_covered_classes():
    body = client.get("/policy").json()
    covered = {c["type"] for c in body["redaction_covered"]}
    assert {"EMAIL", "PHONE", "CREDIT_CARD", "IBAN", "NATIONAL_ID"} <= covered
    assert len(body["redaction_not_covered"]) >= 8


def test_policy_states_the_environment_has_no_real_asr():
    body = client.get("/policy").json()
    assert "No real ASR engine is installed" in body["environment"]
    for dep in ("faster_whisper", "pyannote.audio", "ffmpeg"):
        assert dep in body["environment"]


def test_policy_states_the_heuristic_diarizer_is_not_speaker_identification():
    body = client.get("/policy").json()
    assert "NOT speaker identification" in body["diarization_honesty"]


def test_policy_claims_no_accuracy_numbers():
    body = client.get("/policy").json()
    assert "No WER, DER, precision or recall" in body["accuracy"]
    blob = json.dumps(body).lower()
    for forbidden in ("% wer", "% der", "wer of", "der of", "f1 score of"):
        assert forbidden not in blob


def test_policy_declares_the_no_echo_rule_and_the_ordering_guarantee():
    body = client.get("/policy").json()
    assert "never echoed" in body["manifest_rule"]
    assert "before emission" in body["ordering_guarantee"]
    assert body["pipeline_stages"][:4] == ["ingest", "asr", "diarize", "redact"]


def test_policy_declares_that_the_audio_itself_is_not_redacted():
    gaps = {g["gap"]: g["notes"] for g in client.get("/policy").json()["redaction_not_covered"]}
    assert "the audio itself" in gaps
    assert "TEXT-ONLY" in gaps["the audio itself"]


# ---------------------------------------------------------------------------------------
# /transcribe
# ---------------------------------------------------------------------------------------


def test_auto_refuses_rather_than_silently_serving_a_fixture():
    if FasterWhisperAdapter.availability().available:
        pytest.skip("real ASR is installed in this environment")
    r = client.post("/transcribe", json={"asr": "auto"})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert "no real ASR adapter is available" in detail["error"]
    assert "pip install faster-whisper" in detail["install"]
    assert "fixture" in detail["hint"]


def test_fixture_run_serves_and_is_labelled_not_real_asr():
    r = client.post("/transcribe", json={"asr": "fixture"})
    assert r.status_code == 200
    body = r.json()
    assert body["provenance"]["real_asr"] is False
    assert any("NO REAL ASR" in w for w in body["warnings"])


def test_response_carries_the_checkable_ordering_guarantee():
    body = client.post("/transcribe", json={"asr": "fixture"}).json()
    assert body["guarantees"]["redaction_ran_before_emission"] is True
    assert body["guarantees"]["stages"][3] == "redact"
    assert "audit log" in body["guarantees"]["checked_from"]


def test_transcribe_response_contains_no_raw_pii():
    blob = client.post("/transcribe", json={"asr": "fixture"}).text
    for secret in SECRETS:
        assert secret not in blob


def test_transcribe_manifest_is_span_only():
    body = client.post("/transcribe", json={"asr": "fixture"}).json()
    manifest = body["redaction"]["manifest"]
    assert manifest
    for entry in manifest:
        assert set(entry) == {"type", "detector", "start", "end", "length", "segment_index"}


def test_pyannote_request_503s_with_the_install_command():
    if PyannoteAdapter.availability().available:
        pytest.skip("pyannote.audio is installed in this environment")
    r = client.post("/transcribe", json={"asr": "fixture", "diarizer": "pyannote"})
    assert r.status_code == 503
    assert "pip install" in r.json()["detail"]["install"]


def test_unknown_adapters_are_rejected_with_the_known_list():
    r = client.post("/transcribe", json={"asr": "wav2vec9000"})
    assert r.status_code == 400
    assert "fixture" in r.json()["detail"]
    r = client.post("/transcribe", json={"asr": "fixture", "diarizer": "vibes"})
    assert r.status_code == 400


def test_unknown_fixture_is_a_400_naming_the_available_ones():
    r = client.post("/transcribe", json={"asr": "fixture", "fixture": "nope"})
    assert r.status_code == 400
    assert "pii_sampler" in r.json()["detail"]


def test_missing_audio_file_is_a_400_not_a_500():
    r = client.post("/transcribe", json={"asr": "auto", "audio_path": "/no/such/file.wav"})
    assert r.status_code in (400, 503)  # 503 first if no ASR engine exists at all


def test_store_flag_persists_and_returns_a_transcript_id():
    body = client.post("/transcribe", json={"asr": "fixture", "store": True}).json()
    store_event = next(e for e in body["audit"] if e["stage"] == "store")
    assert store_event["detail"]["transcript_id"]


# ---------------------------------------------------------------------------------------
# /redact — works in every environment, needs no audio
# ---------------------------------------------------------------------------------------


def test_redact_endpoint_works_with_no_speech_dependency():
    r = client.post("/redact", json={"text": "call 07700 900482 or email a@b.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["counts"] == {"PHONE": 1, "EMAIL": 1}
    assert "07700" not in body["text"]


def test_redact_manifest_never_echoes():
    text = ("card 4539 1488 0343 6467, ssn 123-45-6789, iban GB82 WEST 12345698765432, "
            "mobile 07700 900482")
    body = client.post("/redact", json={"text": text}).json()
    blob = json.dumps(body)
    for secret in SECRETS:
        assert secret not in blob
    assert body["manifest_rule"].startswith("type + span only")


def test_redact_is_deterministic():
    payload = {"text": "reach me on +44 20 7946 0958"}
    a = client.post("/redact", json=payload).json()
    b = client.post("/redact", json=payload).json()
    assert a["redacted_sha256"] == b["redacted_sha256"]


def test_person_name_redaction_is_opt_in_and_reports_availability():
    body = client.get("/healthz").json()["redaction"]["person_name_ner"]
    assert body["opt_in"] is True
    r = client.post("/redact", json={"text": "I am Jane Harper", "enable_person_names": True})
    if body["available"]:
        assert r.status_code == 200
        assert "Jane Harper" not in r.json()["text"]
    else:
        assert r.status_code == 503
        assert r.json()["detail"]["reason"]
    # default is OFF, so names survive unless asked for
    assert "Jane Harper" in client.post("/redact", json={"text": "I am Jane Harper"}).json()["text"]
