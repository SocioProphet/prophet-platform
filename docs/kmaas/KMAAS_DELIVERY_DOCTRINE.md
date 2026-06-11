# KMaaS Delivery Doctrine

## Delivery invariant

KMaaS starts with the data plane and domain backbone. Content onboarding comes after canonical identity, policy, and lineage exist. Experience workflows come last.

The sequence is deliberate:

1. Domain backbone.
2. Data plane.
3. Control plane.
4. Systems of record.
5. Text-native content.
6. Audio.
7. Video.
8. Experience workflows.

## Implementation sequence

| Sequence | Layer | Primary action | Output / gate |
|---|---|---|---|
| Seq 0 | Domain | Select anchor domain | Canonical nouns and policy surface |
| Seq 1 | Data plane | Define entities, IDs, lineage | Stable object model and provenance |
| Seq 2 | Control plane | Bind RBAC / ABAC to canonical model | Computable decisions and evidence events |
| Seq 3 | Systems | Onboard HRIS / ERP / CRM / IAM first | Schema contract, cadence, reconciliation |
| Seq 4 | Content | Admit text-native content first | Stable citations and clean evaluation |
| Seq 5 | Experience | Enable agents after prior layers stabilize | Governed copilots and routing |

## Channel ladder

### Phase 0 — admission gates

KMaaS does not index everything. It admits bounded corpora and known formats. Initial supported text formats are plain text, markdown, HTML, JSON, XML, CSV, DOCX, and PDFs with a text layer. Scanned PDFs and image-only documents are out of scope for the initial phase.

### Phase 1 — text

Primary retrieval units are document and paragraph. Optional high-value sentence indexing may be enabled selectively.

Required identifiers:

- `doc_id`
- `doc_rev`
- `span_id`
- `char_range`
- `segmenter_ver`

### Phase 2 — audio

Primary retrieval units are audio file and timecoded segment.

Required identifiers:

- `audio_id`
- `segment_id`
- `start_ms`
- `end_ms`
- `transcript_rev`
- optional `speaker_id`
- optional confidence values

### Phase 3 — video

Primary retrieval units are video, clip, and selectively frame.

Required identifiers:

- `video_id`
- `clip_id`
- `start_ms`
- `end_ms`
- `frame_id`
- `frame_index`
- `fps_assumed`
- `decode_method_ver`

OCR is a post-localization augmentation on retrieved clips or frames, not the ingestion backbone.

## Metric contract summary

| Metric ID | Measure | Unit | Phase target |
|---|---|---|---|
| `TAB.TEXT.GRAN` | text retrieval precision | top-1 accuracy | 80% at doc / paragraph / sentence |
| `TAB.VIDEO.GRAN` | video retrieval precision | success@5 | 65% at video / clip / selective frame |
| `TAB.TEXT.SCALE` | text-source scale | count | 20k / 120k / 800k |
| `TAD.LATENCY.JIT` | end-to-end latency | seconds | 60 / 8 / 1 |
| `TAD.RELEVANCE.JFM` | relevance under rubric | % relevant | 70 / 83 / 98 |

## Measurement protocols

- Text retrieval uses top-1 exact-match accuracy against a labeled gold set at the target retrieval unit.
- Video retrieval uses success@5 or recall@5 with overlap rules against labeled temporal windows.
- Relevance is human-scored with a defined rubric and blinded evaluation where possible.
- Latency is measured end-to-end from request receipt to delivered answer.
- Action count measures discrete user or agent interactions required to produce a correct answer.
- No metric is production-grade without evidence artifacts, logs, and reproducible evaluation runs.

## Phase gates

| Phase | Required state | Channel scope | Acceptance signal |
|---|---|---|---|
| Phase 1 | domain backbone + first system of record + text indexed | text | labeled queries + logs + timing traces |
| Phase 2 | context binding + audio alignment + reranking validated | text + audio | relevance and friction improve vs baseline |
| Phase 3 | sentence precision + video clip retrieval + caching | text + audio + video | provenance intact + near-real-time response |

## Ownership and governance

| Group | Role | Focus | Signal |
|---|---|---|---|
| Leadership / PMO | delivery lead | staffing, milestones, decisions | approved plan + risk log |
| Platform / SRE | platform ops | reliability, telemetry, release health | SLOs + incident path |
| Migration / Data Eng | migration factory | schema, lineage, reconciliation | parity + cutover readiness |
| Controls / Compliance | control review | policy, access, evidence | decisions + audit pack |
| AI / Automation | retrieval + workflow | eval, latency, automation behavior | validated runs + metric trend |
| Customer Success | adoption lead | onboarding, enablement, proficiency | uptake + training status |

## Governance forums

| Forum | Scope | Trigger | Output |
|---|---|---|---|
| Steering | commercial + strategic alignment | milestone or escalation | scope, budget, priority decisions |
| Ops Board | roadmap + release control | regular operating cadence | quality gates + release decisions |
| Controls WG | policy + risk + evidence review | change, incident, audit | access decisions + review package |

## Definition of done

A KMaaS phase is not done because code shipped. It is done when evidence exists, the evidence validates, and the buyer can retain artifacts that prove what happened.

At minimum, every completed phase must produce:

- phase-gate record;
- proof pack;
- metric run result;
- audit-readable summary;
- failure / exception register;
- replay or reproduction path for critical outputs.
