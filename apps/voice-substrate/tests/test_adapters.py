"""Adapter tests — availability probing, honest failure, and the diarization disclaimer.

The point of these is that an unavailable adapter fails LOUDLY and ACTIONABLY. A
transcription substrate that degrades quietly to empty segments hands downstream analytics
an empty transcript to score, which is the exact failure the framework's build order is
trying to prevent.

The suite is written so it passes both here (nothing installed) and on a machine where
faster-whisper and pyannote ARE installed — the availability probe drives the assertion,
not a hard-coded assumption about the environment.
"""
from __future__ import annotations

import pytest

from voice_substrate.asr import (
    AdapterUnavailable,
    Availability,
    FasterWhisperAdapter,
    FixtureAdapter,
    asr_availability,
)
from voice_substrate.diarization import (
    HeuristicDiarizer,
    NullDiarizer,
    PyannoteAdapter,
    diarization_availability,
)
from voice_substrate.types import TranscriptSegment


# ---------------------------------------------------------------------------------------
# Availability probing
# ---------------------------------------------------------------------------------------


def test_availability_probe_never_raises_even_with_the_parent_package_absent():
    """importlib.util.find_spec('pyannote.audio') RAISES when pyannote is missing rather
    than returning None. /healthz must not 500 because of that."""
    for probe in (FasterWhisperAdapter.availability, PyannoteAdapter.availability,
                  FixtureAdapter.availability, HeuristicDiarizer.availability,
                  NullDiarizer.availability):
        result = probe()
        assert isinstance(result, Availability)
        assert result.reason


def test_unavailable_adapters_carry_an_actionable_install_string():
    for probe in (FasterWhisperAdapter.availability, PyannoteAdapter.availability):
        a = probe()
        if not a.available:
            assert a.install, "an unavailable adapter must say how to install it"
            assert "pip install" in a.install or "brew install" in a.install


def test_asr_availability_map_flags_which_adapters_are_real_asr():
    m = asr_availability()
    assert m["fixture"]["available"] is True
    assert m["fixture"]["real_asr"] is False
    assert m["faster_whisper"]["real_asr"] is True


def test_diarization_availability_map_flags_speaker_identification():
    m = diarization_availability()
    assert m["heuristic"]["available"] is True
    assert m["heuristic"]["is_speaker_identification"] is False
    assert m["pyannote"]["is_speaker_identification"] is True
    assert m["none"]["is_speaker_identification"] is False


# ---------------------------------------------------------------------------------------
# Unavailable adapters fail at construction, with the fix in the message
# ---------------------------------------------------------------------------------------


def test_faster_whisper_construction_fails_loudly_when_the_dep_is_missing():
    avail = FasterWhisperAdapter.availability()
    if avail.available:
        pytest.skip("faster-whisper is installed in this environment")
    with pytest.raises(AdapterUnavailable) as ei:
        FasterWhisperAdapter()
    msg = str(ei.value)
    assert "faster_whisper" in msg
    assert "pip install faster-whisper" in msg
    assert ei.value.install


def test_pyannote_construction_fails_loudly_when_the_dep_is_missing():
    avail = PyannoteAdapter.availability()
    if avail.available:
        pytest.skip("pyannote.audio is installed in this environment")
    with pytest.raises(AdapterUnavailable) as ei:
        PyannoteAdapter()
    assert "pyannote" in str(ei.value)
    assert "pip install" in ei.value.install


def test_unavailable_adapter_does_not_degrade_to_empty_output():
    """The anti-pattern this rules out: returning [] so the caller 'succeeds' with nothing."""
    avail = FasterWhisperAdapter.availability()
    if avail.available:
        pytest.skip("faster-whisper is installed in this environment")
    with pytest.raises(AdapterUnavailable):
        FasterWhisperAdapter().transcribe("whatever.wav")


def test_importing_the_package_never_requires_a_speech_dependency():
    import voice_substrate  # noqa: F401  — the import itself is the assertion

    assert voice_substrate.__version__


# ---------------------------------------------------------------------------------------
# Fixture adapter — usable, and unmistakably not ASR
# ---------------------------------------------------------------------------------------


def test_fixture_adapter_is_labelled_as_not_real_asr():
    a = FixtureAdapter()
    assert a.name.startswith("fixture:")
    assert "NOT real speech recognition" in FixtureAdapter.availability().reason


def test_fixture_adapter_ignores_the_audio_path_entirely():
    a = FixtureAdapter()
    assert a.transcribe("/nonexistent/path.wav") == a.transcribe(None)


def test_fixture_adapter_names_the_available_fixtures_when_one_is_missing():
    with pytest.raises(FileNotFoundError) as ei:
        FixtureAdapter(fixture="does_not_exist")
    assert "pii_sampler" in str(ei.value)


def test_fixture_adapter_accepts_injected_segments():
    segs = [TranscriptSegment(0.0, 1.0, "hello")]
    assert FixtureAdapter(segments=segs).transcribe(None) == segs


# ---------------------------------------------------------------------------------------
# Heuristic diarizer — real but modest, and it says so
# ---------------------------------------------------------------------------------------


def _segs(*spans: tuple[float, float]) -> list[TranscriptSegment]:
    return [TranscriptSegment(s, e, f"segment at {s}") for s, e in spans]


def test_heuristic_alternates_speakers_across_a_silence_gap():
    out = HeuristicDiarizer(gap_seconds=0.75).assign(_segs((0.0, 2.0), (4.0, 6.0), (8.0, 9.0)))
    assert [s.speaker for s in out] == ["speaker_0", "speaker_1", "speaker_0"]


def test_heuristic_keeps_one_speaker_when_segments_run_on():
    out = HeuristicDiarizer(gap_seconds=0.75).assign(_segs((0.0, 2.0), (2.1, 4.0), (4.2, 6.0)))
    assert {s.speaker for s in out} == {"speaker_0"}


def test_heuristic_supports_more_than_two_speakers():
    out = HeuristicDiarizer(gap_seconds=0.5, num_speakers=3).assign(
        _segs((0.0, 1.0), (2.0, 3.0), (4.0, 5.0), (6.0, 7.0))
    )
    assert [s.speaker for s in out] == ["speaker_0", "speaker_1", "speaker_2", "speaker_0"]


def test_heuristic_declares_itself_not_speaker_identification():
    d = HeuristicDiarizer()
    assert d.is_speaker_identification is False
    assert "not speaker identification" in " ".join(d.warnings()).lower()
    assert "no audio" in d.method or "no voice model" in d.method


def test_heuristic_documented_failure_mode_a_pausing_speaker_is_relabelled():
    """This is the known false split, pinned so nobody 'fixes' the test instead of the
    disclaimer: one person pausing to think looks identical to a turn change."""
    out = HeuristicDiarizer(gap_seconds=0.75).assign(_segs((0.0, 3.0), (5.0, 8.0)))
    assert out[0].speaker != out[1].speaker  # same human in reality; the heuristic cannot tell


def test_heuristic_documented_failure_mode_an_interruption_is_missed():
    out = HeuristicDiarizer(gap_seconds=0.75).assign(_segs((0.0, 3.0), (3.05, 5.0)))
    assert out[0].speaker == out[1].speaker  # two humans in reality; no pause to detect


def test_heuristic_rejects_nonsense_configuration():
    with pytest.raises(ValueError):
        HeuristicDiarizer(gap_seconds=0)
    with pytest.raises(ValueError):
        HeuristicDiarizer(num_speakers=0)


def test_null_diarizer_assigns_nothing_and_says_so():
    out = NullDiarizer().assign(_segs((0.0, 1.0), (5.0, 6.0)))
    assert all(s.speaker is None for s in out)
    assert "no diarization" in " ".join(NullDiarizer().warnings()).lower()


def test_pyannote_requires_audio_because_it_clusters_voice():
    """Even with the dep installed, diarization from text alone is not a thing — the
    adapter refuses rather than inventing labels."""
    if not PyannoteAdapter.availability().available:
        pytest.skip("pyannote.audio not installed; construction path covered above")
    with pytest.raises(ValueError, match="needs the audio file"):
        PyannoteAdapter().assign(_segs((0.0, 1.0)), None)
