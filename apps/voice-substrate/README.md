# voice-substrate

ASR + diarization + redaction for prophet-platform. This is **step 1** of the build order in
*Needs vs Wants: An Instrumented Framework for Voice + Text Analytics* §10.3 — "ingest audio +
metadata; ASR; diarization; redaction; storage; audit log" — and it exists because the estate
had no voice capability at all: everything downstream was text-only.

§10.2 of the same framework names the trap this is built to avoid: *"trying to do 'personality'
before you can do 'transcription'"*. So nothing in this package infers anything about a speaker.
It transcribes, attributes turns, removes PII, stores the result, and writes an audit log. That
is the whole scope, on purpose.

---

## Read this first: what actually runs here

**No real ASR engine is installed in this environment.** Verified, not assumed:

| dependency | status | what it would enable |
|---|---|---|
| `faster_whisper` | not importable | real transcription (`FasterWhisperAdapter`) |
| `whisper` | not importable | — |
| `vosk` | not importable | — |
| `pyannote.audio` | not importable | real speaker diarization (`PyannoteAdapter`) |
| `ffmpeg` | not on `PATH` | audio decoding for any of the above |

So today the only end-to-end path is **`FixtureAdapter`** (canned transcript replay — *not*
speech recognition) plus the redactor, which is pure Python and runs everywhere.

What that means concretely:

* `FasterWhisperAdapter` and `PyannoteAdapter` are **real, correct code against the documented
  APIs of those libraries** — they have simply never been executed on this machine. They are
  labelled as unverified in their own docstrings rather than presented as working.
* Both **fail loudly at construction** with the exact install command. Neither degrades to empty
  segments. A transcription substrate that silently returns nothing hands downstream analytics an
  empty transcript to score, which is worse than an error.
* `POST /transcribe` with `asr: "auto"` **503s** with that install command. It does *not* fall
  back to the fixture. A caller asking for transcription must never receive canned text that
  looks like a transcript.
* `GET /healthz` reports live, per-adapter availability, so an operator sees the degradation up
  front instead of discovering it from a confusing runtime error.

**No accuracy number is claimed anywhere** — no WER, no DER, no PII precision or recall. There is
no labelled evaluation set for speech or for PII in this estate, so any such figure would be
fabricated. The structural validators (Luhn, IBAN mod-97, SSN issuing ranges) are exact by
construction; nothing else here has been measured against ground truth.

To enable the real thing:

```bash
pip install faster-whisper==1.0.3          # + brew install ffmpeg
pip install 'pyannote.audio==3.3.2'        # + HF token, + accept the gated model terms
```

Nothing else changes: the pipeline, the redactor, the service and the tests are all written
against adapter protocols, so installing a dependency is the entire migration.

---

## Architecture

```
audio ──▶ AsrAdapter ──▶ DiarizationAdapter ──▶ Redactor ──▶ emit sinks ──▶ TranscriptStore
                                                    │
                                                    └─▶ audit log (every stage, in order)
```

Same substrate/instrument separation as `needs-wants-instrument/src/needs_wants/substrate.py`:
the pipeline knows the *contract*, never the engine. Swapping faster-whisper for whisper.cpp or a
hosted API touches one class.

### 1. ASR — `asr.py`

`AsrAdapter` protocol: `(audio_path) -> list[TranscriptSegment]`, each segment carrying `start`,
`end`, `text`, optional `speaker` and `confidence`.

* **`FasterWhisperAdapter`** — CTranslate2 Whisper. Lazy import at call time, so importing this
  package never needs the dep. Not runnable here.
* **`FixtureAdapter`** — replays a canned transcript from `fixtures/`. **This is not ASR**; no
  audio is decoded. Its `name` is prefixed `fixture:` and `provenance.real_asr` is `false` on
  every result, so a fixture run can never be mistaken for a transcription in a stored artifact.

### 2. Diarization — `diarization.py`

`DiarizationAdapter` protocol: assigns speaker labels to segments.

* **`PyannoteAdapter`** — real diarization (voice-embedding clustering), attributing each ASR
  segment to the turn it overlaps most. Not runnable here.
* **`HeuristicDiarizer`** — **not speaker identification.** It never opens the audio. It walks
  segments in time order and advances the speaker label whenever the gap to the previous segment
  exceeds a threshold. That is turn segmentation that happens to produce speaker-shaped labels.
  Named failure modes, all expected:
  * a speaker pausing mid-thought is relabelled as a different speaker;
  * a speaker change with no pause (interruption, overlap) is missed entirely;
  * labels are **positional, not identities** — `speaker_0` early and `speaker_0` later are not
    guaranteed to be the same person, because there is no voice model to re-identify with. Do not
    aggregate per-speaker statistics across a transcript from these labels;
  * the speaker count is assumed, not detected;
  * overlapping speech is not representable.

  `is_speaker_identification` is `False` and every result it labels carries a warning saying so.
* **`NullDiarizer`** — assigns nothing. The honest default when nothing is known.

### 3. Redaction — `redaction.py`

The one stage that is genuinely production-grade, deliberately: it has no third-party dependency,
so its guarantee is not conditional on an install.

**Covered classes** (also served by `GET /policy`):

| class | method |
|---|---|
| `EMAIL` | written form, plus **spoken form** (`jane dot harper at example dot com`) |
| `PHONE` | E.164/international, NANP separated + compact, UK/EU trunk, cue-introduced; filtered to 7–15 digits |
| `CREDIT_CARD` | 13–19 digit runs **validated with Luhn** — non-Luhn runs are not redacted as cards |
| `SPOKEN_CARD_NUMBER` | digit-word runs that reconstruct to a Luhn-valid card number |
| `SPOKEN_NUMBER_SEQUENCE` | runs of ≥7 spoken digits, incl. `double`/`triple` repeaters and mixed numeric output |
| `IBAN` | ISO 13616 **mod-97 validated** |
| `NATIONAL_ID` | US SSN with issuing-range exclusions, UK NINO, cue-introduced identifiers (passport, licence, TFN, NHS, Aadhaar, Medicare) |
| `DATE_OF_BIRTH` | numeric and textual dates preceded within 80 chars by a birth cue |
| `STREET_ADDRESS` | numbered street lines, PO boxes, UK postcodes, US state+ZIP |
| `PERSON_NAME` | **opt-in only**, requires spaCy + `en_core_web_sm`; NER recall is partial |

**The ASR-specific case.** A redactor written for typed text misses most numeric PII in a
transcript, because ASR emits `four one three five five five oh one three four`, not
`413-555-0134`. `spoken_number_runs()` handles digit-word runs, expands `double`/`triple`
repeaters, and copes with the half-normalised output real engines produce (`413 five five five oh
one three four`). It requires at least one genuine digit *word* in a run — so `in 2026 we shipped
1500 units` is not glued into a false positive — and it refuses to *start* a run on the
homophones ASR emits constantly in ordinary speech (`to`, `too`, `for`, `fore`, `ate`), accepting
them only as continuations of an established run.

**False positives.** Structural checks run wherever the format supports one; that is what stops a
16-digit order reference being reported as a card. Where no check exists (addresses, phones) the
detectors lean toward over-redaction: a false positive costs a redacted street name, a false
negative costs a disclosure.

**Nothing is echoed.** A `RedactionFinding` carries `type`, `detector`, `start`, `end`, `length`
and `segment_index` — and no field that could hold the matched value, by construction. The estate
rule is that scanners never echo their matches; a manifest quoting the card number it found would
just relocate the leak into the audit trail.

**Not covered** — declared in full on `GET /policy` and pinned by tests. The headline items:

* **the audio itself.** Redaction is text-only. The submitted audio is never modified and still
  contains the speaker's voice, which is itself biometric identifying data.
* spoken dates of birth (*"born on the fourth of July nineteen eighty two"*).
* compound spoken numbers (*"twenty three forty five"*) — only single digit-words plus repeaters.
* non-English digit words; NATO-style spelled-out alphanumerics.
* organisation names; medical record / policy / account numbers; vehicle registrations.
* person names by default (opt-in, and partial even then).
* **quasi-identifiers** — a transcript can identify someone through combination (employer + role +
  rare condition) with no single redactable span. **Redaction is not anonymisation.**
* **measured precision/recall** — see above.

### 4. Pipeline + storage — `pipeline.py`, `storage.py`

Redaction is not a filter applied to output; it is a stage raw text cannot get past. Four
enforcement mechanisms, not one:

1. **Type separation.** `TranscriptSegment` (raw) and `RedactedSegment` are different types, and
   `PipelineResult` can only hold the latter — so a pipeline that skipped redaction has nothing
   to build a result from.
2. **Local scope.** The raw segment list is a local inside `run()`, deleted after redaction. It is
   never assigned to the result, handed to a sink, or passed to the store.
3. **Sinks run after.** Downstream consumers register via `emit_sinks` and are invoked in the
   `emit` stage, entered only once `redact` has returned.
4. **The audit log.** Every stage is recorded in order with the redaction manifest summary, so the
   ordering is *checkable from the artifact* — `redaction_precedes_emission(result)` reads the
   emitted audit log, not the source, and an auditor can run it against a stored transcript with
   no access to this repository.

`FilesystemTranscriptStore` / `InMemoryTranscriptStore` **refuse** to persist a result whose
redaction stage did not run. Storage is where a transcript stops being a transient value and
becomes a durable disclosure, so that is the right place for a hard gate.

Caller-supplied metadata is recorded by **key only** — it routinely carries participant names and
phone numbers and does not pass through the transcript redactor.

---

## HTTP API

```
GET  /healthz            per-adapter availability in THIS process, with reasons and install hints
GET  /policy             redaction classes covered AND not covered; environment + accuracy honesty
POST /transcribe         { audio_path?, asr, diarizer, fixture?, store?, metadata? }
POST /redact             { text } -> redacted text + span-only manifest (no audio, no ASR needed)
POST /transcribe/upload  multipart — registered only when python-multipart is installed
```

Run it:

```bash
pip install -r requirements.txt
uvicorn voice_substrate.server:app --app-dir src --port 8087
```

Exercise the full pipeline with no speech dependency at all:

```bash
curl -s localhost:8087/transcribe -H 'content-type: application/json' \
     -d '{"asr":"fixture","diarizer":"heuristic"}' | jq '.redaction.counts, .warnings'
```

---

## Tests

```bash
pip install -r requirements-test.txt
python -m pytest tests/ -q
```

**149 passed, 1 skipped** — the skip is the pyannote path, which is skipped only because the
dependency is absent (it runs where pyannote is installed). The suite needs no ASR dependency and
no network.

Coverage of the things that matter:

* `test_redaction.py` — every PII class; Luhn true and **false** positives; IBAN mod-97 true/false;
  SSN never-issued ranges; overlap priority; the manifest never containing a raw value (both
  structurally and behaviourally); no false positives on ordinary speech.
* `test_spoken_digits.py` — digit-word runs, `double`/`triple` expansion, mixed numeric output,
  the homophone guard, the length threshold, and Luhn classification of spoken card numbers.
* `test_adapters.py` — availability probes never raise (`find_spec('pyannote.audio')` *raises*
  when pyannote is absent); unavailable adapters fail with an install command and never degrade to
  empty output; the heuristic diarizer's documented failure modes are pinned so nobody "fixes" the
  test instead of the disclaimer.
* `test_pipeline.py` — fixture end-to-end; downstream sinks receive redacted segments only; no raw
  value survives anywhere in the serialized result; audit ordering; the store refusing unredacted
  writes.
* `test_server.py` — `/healthz` degradation honesty, `/policy` covered-and-not-covered, `auto`
  refusing rather than serving a fixture, 503s naming the install.

---

## What this is not

Not a speaker-inference layer, not analytics, not a "personality" surface. Those are later steps
in §10.3, and they are downstream of a transcription layer that works and a redaction stage that
provably ran. This is that layer.
