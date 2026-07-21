# Digital Health Twin — the "Digital Health Self"

> Status: **DESIGN CAPTURE** (not started). Opt-in, local-first, sovereign. Captured 2026-07-21.
> Owner decision pending: start now vs. finish in-flight work first.

## The idea (Michael, 2026-07-21)

A **medical digital twin** of a person — represented visually like an anatomical body diagram
(the organ-map posters) — that:

- **Captures every medical interaction**: clinical notes, lab results, X-rays, MRIs/CTs (DICOM),
  discharge summaries, prescriptions, immunizations, genetic reports, wearable/vitals streams — and
  any other media associated with a medical encounter.
- **Stores a lifetime of case records in one place**, **local-first**, so the record is the
  person's, not a hospital's silo.
- Lets **the person and their designated agents reason over it** — timelines, trends, "pull my
  cardiology history," "summarize the last 3 years," "what changed since my last MRI."
- Is **strictly opt-in** and consent-governed — this is the most sensitive data class there is (PHI).
- Is rendered as a **"digital health self"** — the body/organ diagram is the living index into the
  record, not a static picture.

This is **not** a diagnostic tool. It **organizes, stores, retrieves, and governs sharing** of a
person's own records. A clinician diagnoses; the twin never does. (Non-diagnostic framing is a
first-class product constraint, not a disclaimer bolted on.)

## Where it sits in the estate

This is the **records + media substrate** of the Human Digital Twin the estate already models:

- `project_hdt_body_state_model` — HDT = a state model `x(t)`. **This is where the observations that
  drive `x(t)` come from** (labs → LOINC observations, imaging → findings, etc.).
- Studio **Governance → HDT human twin** already runs an OmegaState lattice over `HdtObservation`s
  keyed by **LOINC codes** (`ABSENT→...→DELIVERED`, only a human/clinician canonizes). The Digital
  Health Self is the **capture/ingest + storage + media** layer that feeds those observations, and
  the promotion membrane is already the right governance metaphor.
- `project_digital_soul_identity_reputation` (identity = 64-gate correspondence lattice),
  `project_personal_knowledge_graph` (person-graph), `project_memory_distribution_grant` (memory-mesh
  3-axis governance with read-enforced revocation), the **Capability Membrane** (#701: gate →
  ExecutionDecision + sealed receipt) — these are the consent/governance spine this reuses wholesale.
- `project_bearbrowser_cockpit` — "sovereign life control plane." The Digital Health Self is a plane
  **inside** that cockpit; the local-first store rides the BearBrowser sidecar/sovereign-node model.
- Existing surfaces `DigitalTwin.vue` (`/analytics/digital-twin`) + `HolographMe.vue` are adjacent —
  reconcile/absorb, don't duplicate. This new thing is the **health** twin specifically.

**One-line thesis:** *Apple Health / Epic MyChart, but sovereign, local-first, standards-native, and
proof-carrying — the record is yours, agents read it only under a revocable, receipted grant, and
the body diagram is the interface.*

## Pillars

### 1. Local-first, sovereign, encrypted storage
- PHI **never leaves the user's node** unless they grant it. Encrypted at rest.
- **Content-addressed, hash-sealed** media (X-ray/MRI/note = a blob keyed by its hash) → every
  artifact is tamper-evident and citable, reusing the estate's receipt/provenance moat.
- Portable export (the user can take the whole twin and leave — anti-lock-in).

### 2. Standards-native ingest (a lifetime, normalized)
- **FHIR R4** as the canonical record model: `Patient, Encounter, Observation, Condition, Procedure,
  DiagnosticReport, ImagingStudy, DocumentReference, MedicationStatement, AllergyIntolerance,
  Immunization`.
- **DICOM** for imaging (X-ray/MRI/CT/US); **C-CDA / PDF** for documents (extractive OCR, reusing the
  OCW capture engine pattern — quote, don't hallucinate).
- Coding systems: **LOINC** (labs — already the estate's hook), **SNOMED CT** (conditions/procedures),
  **RxNorm** (meds), **CPT/ICD-10** (billing/dx codes).
- Import lanes: **SMART-on-FHIR** (connect a provider portal), **Apple Health / Google Health
  Connect** (wearables + phone-aggregated records), **DICOM import**, **manual upload**.

### 3. The anatomical twin as the interface
- The organ/body diagram is the **navigation index**: each organ/system is a node; records attach to
  organs → systems → encounters → a lifetime **timeline**.
- Click **heart** → cardiology encounters, ECGs, cholesterol **trend sparklines**, cardiac imaging.
- **Reuses the design-language anneal components 1:1** (this is a big reason the timing is good):
  - **Health timeline** = the `ExecutionTimeline` gantt pattern (encounters/procedures over time).
  - **Lab trends** = `Sparkline` (a value's trajectory; ranges as the "compared-to-what" band).
  - **Organ / condition factsheet** = `FactsheetDrawer` + an **attested** (deterministic, receipted,
    non-diagnostic) summary.
  - **Care-pathway lineage** = `LineageDag` (referral → test → dx → treatment as a real DAG).
  - **Record status** = the **epistemic stripe** (observed / verified-by-lab / attested-by-clinician).
  - **Promotion membrane** = record trust promotion (self-reported → clinician-confirmed).

### 4. Governed reasoning by human + designated agents
- Agents get **scoped, revocable, receipted** access to slices ("my cardiology records 2020–2024,
  read-only, expires in 30 days") via the **Capability Membrane** + **Memory Distribution Grant**.
- **Every agent read emits a receipt**; **read-enforced revocation** (revoke → future reads blocked,
  and the grant record shows what was accessed when).
- This is the sovereign difference vs. every incumbent: consent is cryptographic and auditable, not a
  checkbox in a vendor's TOS.

### 5. Attested, non-diagnostic summaries
- Any summary over the twin is **provenance-carrying** and **explicitly not medical advice**.
- Deterministic/extractive where possible (like the Catalog's attested factsheet). Where a model is
  used, output is labeled model-generated, cites the source records, and never asserts a diagnosis.

## Architecture sketch (walking skeleton, when we build)

```
BearBrowser / sovereign node (LOCAL-FIRST)
├── health-twin service (local)
│   ├── FHIR store (canonical records)           ← the graph of the person's health
│   ├── DICOM store + blob store (hash-sealed)    ← imaging + note media
│   └── health graph → HellGraph facts            ← each record a proof-carrying node
├── ingest adapters
│   ├── SMART-on-FHIR connector (provider portals)
│   ├── Apple Health / Google Health Connect
│   ├── DICOM import
│   └── document OCR (extractive)
├── consent / governance
│   ├── Capability Membrane (gate → ExecutionDecision + sealed receipt)
│   └── Memory Distribution Grant (3-axis, read-enforced revocation)
└── surface: HealthTwin.vue
    ├── anatomical body index (organs/systems → records)
    ├── lifetime timeline (gantt) + lab trends (sparklines)
    ├── organ/condition factsheet drawer (attested, non-diagnostic)
    ├── DICOM viewer (imaging)
    └── governed-share panel (grants + receipts + revoke)
```

Ontology: map organs/systems to **Ontogenesis + a medical ontology (SNOMED CT / body-structure
hierarchy)**; labs via LOINC; the same epistemic ramp for record trust.

## Hard problems / open questions (to resolve in a design spike before building)
1. **Storage substrate**: what is the local-first PHI store on the sovereign node? (encrypted FHIR
   server? SQLite+FHIR? content-addressed blob for DICOM?) How does it sync to the BearBrowser sidecar
   without ever touching a vendor cloud?
2. **Regulatory posture**: PHR (personal health record) tool, explicitly **not** a medical device.
   HIPAA applies to covered entities, not to the individual holding their own record — but if we ever
   help *transmit* to a provider/agent, the consent + audit trail must be airtight. Get this framing
   right up front.
3. **DICOM viewing** locally (cornerstone.js-class viewer, self-contained / offline).
4. **Consent granularity**: per-record? per-organ/system? per-date-range? per-code-system? The grant
   model has to be understandable by a non-technical person **and** cryptographically enforced.
5. **De-identification** for any research/commons contribution (opt-in, separate, never default).
6. **Trust promotion**: self-reported vs. lab-verified vs. clinician-attested — the epistemic ramp +
   promotion membrane, but who/what is allowed to promote to "attested"?

## ⭐ The anatomical visual model is FIRST-CLASS (under-scoped in v1 — corrected 2026-07-21)

The centerpiece of a "digital health *self*" is a **body that looks like the person, that you can look
*into*, system by system** — exactly the anatomical organ-map posters Michael shared. The first
skeleton (#932) led with the data/consent plane and reduced anatomy to a list of system chips; the
body was punted to a footnote. **That was the wrong emphasis.** The visual model IS the product.

Requirement:
- A **representative human figure** on-screen with **switchable, separable anatomical layers** you can
  view into — skeletal, muscular, cardiovascular, respiratory, nervous, digestive, urinary, endocrine,
  lymphatic — like Complete Anatomy / BioDigital Human, but sovereign + local-first.
- **Organs are the index into records** — click the heart → cardiology records — on the model itself.
- **Personalization ("looks like them"):** body-shape parameters from the person's own metrics
  (height/weight/measurements), skin tone, and (opt-in, later) an optional face/likeness. All local.

Production path (NOT hand-drawn SVG — that carries the concept, not the fidelity):
- A rigged **3D parametric human** (MakeHuman / SMPL-class body, glTF) rendered in-browser with
  **three.js**, rotatable, with real per-system meshes toggled as layers. Self-contained/offline.
- Interim: a higher-fidelity **layered 2D anatomical illustration set** (open medical-illustration
  source) can bridge before the 3D model lands.
- An interactive SVG PoC (layers + clickable organs + record links + skin-tone stub) was built in-chat
  2026-07-21 to validate the interaction model — treat it as a wireframe, not the target.

## Guardrails (non-negotiable)
- **Opt-in only.** Nothing is captured or shared without explicit, per-class consent.
- **Local-first, sovereign, encrypted.** No vendor cloud by default; the user can export and leave.
- **Non-diagnostic.** Organizes/retrieves records; never diagnoses or advises.
- **Every access receipted; revocation enforced on reads.**
- **Never publish/share PHI** to any external service without an explicit, scoped grant.

## Why the timing question is real
The design-language anneal (PRs #927–931) just built **exactly the components this needs** (timeline,
sparkline, factsheet drawer, lineage DAG, epistemic stripe, promotion membrane) and the consent spine
(Capability Membrane, Memory Distribution Grant) already exists. So a walking skeleton is unusually
cheap right now. **But** it's a large, sensitive, standards-heavy program that deserves a real design
spike (storage + regulatory + consent model) before code — not a rushed mid-stream bolt-on.
Recommendation: **land the in-flight anneal, then start this as its own program with a spike →
skeleton**, rather than interleaving it now.
