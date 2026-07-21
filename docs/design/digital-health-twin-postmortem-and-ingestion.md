# Why HealthVault and Watson Health died — and the ingestion architecture that answers it

> The hard walls are ingestion-at-scale, regulatory, clinician workflow, and trust. Before building the
> ingestion plane, we name exactly what killed the two most-funded attempts at this — because the
> post-mortem *is* the architecture spec. Status: capture 2026-07-21. Non-diagnostic PHR posture.

---

## Part 1 — The deeper truth (not the obituary headline)

The surface obituaries are "low consumer adoption" (HealthVault) and "Watson for Oncology gave unsafe
recommendations, MD Anderson cancelled" (Watson Health). Both are true and both are shallow. The real
causes are structural, and they are *opposite* failures that our architecture has to answer at the same
time.

### Microsoft HealthVault (2007–2019) — **a vault with no brain**
- **It was a filing cabinet, not a product.** It *stored* records; it never *did* anything with them.
  A place to put data is not a product — a thing that acts on data is. No reasoning, no insight, no
  action returned to the person.
- **Cold-start / empty-vault death spiral.** Population was manual and patient-mediated with no
  automated ingestion. Empty vault → no value → no reason to fill it → empty vault. Two-sided market
  (consumers *and* providers/devices) bootstrapped from neither side.
- **No wedge into the clinical workflow.** It sat *outside* the EHR. Providers had no reason to push
  data in or pull value out; data that went in never came back as value to a clinician or the person.
- **It was too early — the rails did not exist yet.** HealthVault predates **FHIR / SMART-on-FHIR**
  (2015+), **USCDI/US Core**, the **21st Century Cures Act** information-blocking rule (2016, enforced
  2020+), **TEFCA** (2023), and **Blue Button 2.0**. It had to *beg* every provider for data through
  bespoke integrations. Today the law *compels* providers to expose a patient-access API. Google Health
  (2008–2012) died the identical death in the identical pre-rails window.

**One-line cause: data without reasoning, populated by hand, outside the workflow, before the
interoperability floor existed.**

### IBM Watson Health (2015–2022) — **a "brain" bolted onto un-unified silos, sold before it worked**
IBM spent >$4B acquiring Phytel, Explorys, Merge Healthcare, and Truven Health Analytics, and sold the
pile to Francisco Partners for ~$1B. The deeper truths — several of which are only visible from inside:

1. **It was an acquisition rollup wearing an AI brand, with no unified substrate.** Four companies,
   four incompatible data models, four codebases, four sales orgs, spray-painted "Watson." There was
   never a shared ontology underneath. **You cannot bolt a reasoning layer onto un-unified data** — and
   they never unified it. "Sold off for parts" is the natural end of a thing that was *always* parts.
2. **It encoded one institution's practice as universal truth, with no provenance.** Watson for
   Oncology was trained largely on a small set of hypothetical/synthetic cases curated at a single
   center — MSK's practice patterns presented as authoritative, black-box, one-size recommendations.
   No way to say *"this is one institution's opinion — tier: institutional-practice — not verified
   evidence."* **No provenance, no epistemic humility, no proof.** So when it was wrong it was
   confidently, un-interrogably, liability-invitingly wrong.
3. **It was a services-revenue vehicle, not a product.** IBM's incentive structure rewards booking
   large consulting engagements and multi-year licenses to hospital CIOs on the strength of the brand,
   then billing services hours to make it work *per site*. The thing was **sold before it worked** and
   never productized — bespoke at every deployment, scalable at none. The "shitty company" instinct has
   a precise mechanism: **the money was in the sales relationship and the services hours, not in
   shipping working software**, so working software was never the actual objective.
4. **Opaque to the only person who mattered — the clinician.** No citations, no reasoning trace. A
   black box a doctor cannot interrogate is a black box a doctor will not trust, correctly.
5. **The patient was never a party.** Pure enterprise B2B — hospitals and payers. No consent primitive,
   no data-owner in the loop, no trust surface. Data was extracted, never returned.
6. **Regulatory posture confusion.** It flirted with diagnosis (a medical-device claim) while branding
   itself "decision support" — carrying the liability of the former with the evidence of neither.

**One-line cause: reasoning without a unified, provenanced substrate; institutional bias sold as truth;
a services business wearing a product costume; the patient absent.**

### The synthesis — and why it maps 1:1 onto our thesis
The two failures are mirror images:

| | HealthVault | Watson Health |
|---|---|---|
| Had | the vault (storage) | the "brain" (reasoning) |
| Missing | any reasoning / action | a unified, provenanced substrate |
| Data | hand-entered, empty | rolled-up silos, un-unified |
| Provenance | n/a | **absent** — bias sold as truth |
| Patient | passive | **absent** |
| Business | product with no value loop | **services vehicle, not product** |
| Timing | pre-rails (no FHIR/Cures) | rails existed, ignored them |

**Neither had the one thing that defines ours: a unified, ontology-typed, *provenanced* substrate with
a proof-carrying, epistemically-honest reasoner on top of it, the patient sovereign and in the loop,
shipped as a product on top of the mandated interoperability floor.** HealthVault had the vault and no
brain; Watson had the "brain" and no honest vault. We build substrate + reasoner + provenance + consent
as **one coherent thing**, patient-owned, riding rails (SMART-on-FHIR, USCDI v6, TEFCA IAS, Blue Button)
that did not exist when HealthVault was begging for data.

---

## Part 2 — The seven design mandates the post-mortem forces

1. **Reasoning is the product, not storage.** The vault only earns its place because a proof-carrying
   reasoner acts on it. (Answers HealthVault #1.)
2. **Automated ingestion on the mandated rails — no manual empty-vault.** SMART-on-FHIR patient access,
   TEFCA Individual Access Services, Blue Button, DICOMweb, wearable APIs. (Answers HealthVault #2, #4.)
3. **Provenance on every single fact — non-negotiable.** Source, connector, auth model, retrieval time,
   the exact source shape, the USCDI class. No fact without its lineage. (Answers Watson #2, #4.)
4. **Epistemic tiering — never sell one source's opinion as truth.** device-measured / lab-verified /
   clinician-attested / patient-entered / derived, each labeled and colored, promotable only with
   evidence. (Answers Watson #2.)
5. **Unified substrate first — one ontology, not a rollup.** Everything normalizes to USCDI v6 + the
   HDT/health ontology *before* it lands. No silo bolt-ons. (Answers Watson #1.)
6. **Patient sovereign and in the loop — consent, receipts, revocation.** The data owner is the primary
   party; every access is receipted; revocation is enforced on reads. (Answers Watson #5, both trust.)
7. **Product, not services; non-diagnostic, honestly scoped.** It works out of the box the same way for
   everyone; it organizes/retrieves/governs and never diagnoses. (Answers Watson #3, #6.)

---

## Part 3 — The ingestion architecture: prove every connector *without* their live data

The user's directive: **bury the field by meeting or beating every feature; where a feature needs a
data feed we don't have, build it anyway — modular enough to drop in paid or open data later — and
prove the functionality against the real API's documented schema without their live data.**

### The fixture → sandbox → live adapter model
Every source (Apple Health, Google Health Connect, Oura, Fitbit, Dexcom, Withings, Epic/SMART-on-FHIR,
CMS Blue Button, DICOMweb, C-CDA, manual) is a **`Connector`** with two separated halves:

- **`fetch(mode)`** — the *transport*. This is the only part that differs by mode:
  - `fixture` — reads a bundled payload **shaped exactly like the real API's documented response**
    (HealthKit `HKQuantitySample`, Oura v2 `daily_sleep` doc, FHIR R4 US Core `Bundle`, Blue Button
    `ExplanationOfBenefit`, DICOMweb QIDO-RS tag JSON). No credentials, no PHI, no contract.
  - `sandbox` — hits the vendor's public sandbox (SMART sandbox, Blue Button sandbox, Dexcom sandbox,
    Metriport sandbox) with synthetic patients.
  - `live` — hits production with the person's OAuth grant / on-device export.
- **`normalize(raw)`** — the *adapter logic*. **Identical across all three modes.** It maps the real
  provider shape → our canonical, USCDI-typed, ontology-IRI'd, provenance-stamped records.

**The load-bearing insight:** because `normalize` is identical in fixture and live mode, *a connector
that correctly normalizes a real-schema fixture has a proven live path.* We validate the entire
pipeline — ingest → normalize → USCDI-type → ontology-IRI → localize-to-organ → land-in-twin → reason —
with zero paid feeds and zero real PHI. Flipping to live is `mode = 'live'` plus a credential. This is
how we build the whole superset now and integrate real feeds (open, paid, or patient-authorized) later,
one connector at a time, without ever blocking on a contract.

### What ships in the walking skeleton (this increment)
`apps/health-twin/src/ingest.ts` (framework) + `src/connectors/*` (five real-schema adapters):

| Connector | Kind | Auth model (live) | Real source shape (fixture matches) | USCDI classes yielded |
|---|---|---|---|---|
| `apple-health` | wearable | HealthKit on-device export | `HKQuantitySample` / `HKCategorySample` | Vital Signs (HR, RHR, HRV, SpO2, BP, VO2max, weight, steps, sleep) |
| `oura` | wearable | OAuth2 (Oura API v2) | `/v2/usercollection/daily_*` docs | Vital Signs (RHR, HRV, SpO2, sleep, activity) |
| `epic-smart-fhir` | ehr | **OAuth2 SMART-on-FHIR** (patient access) | FHIR R4 US Core searchset `Bundle` | Problems, Labs, Medications, Allergies, Immunizations |
| `cms-blue-button` | claims | OAuth2 (Blue Button 2.0) | FHIR `ExplanationOfBenefit` + `Coverage` | Medications (Part D fills), Health Insurance |
| `dicomweb` | imaging | DICOMweb QIDO-RS | QIDO-RS study/series tag JSON | Diagnostic Imaging |

Each record lands with a **`Provenance`** stamp (source, connector, authModel, mode, retrievedAt,
sourceShape, uscdi) and an **epistemic tier** — so the very first fact the twin ingests already carries
the lineage Watson never had. `epic-smart-fhir` is the marquee adapter: SMART-on-FHIR patient access is
the **legally-clean, mandated path** (TEFCA Individual Access Services), the exact rail HealthVault
lacked and the one the aggregators are being *litigated* for abusing under a "treatment" purpose.

### Sequencing (one wall at a time, per the user)
1. **Ingestion (this increment)** — the connector framework + 5 real-schema adapters, proven on
   fixtures, provenance + USCDI + ontology on every record. ← *now*
2. **Normalization/reconciliation at scale** — cross-source dedup, unit harmonization (UCUM), MPI-style
   identity match, C-CDA→FHIR conversion (fork Metriport's AGPLv3 converter).
3. **Clinician workflow** — SMART-on-FHIR app launch + CDS Hooks (push the twin's cited, tiered insight
   into the EHR at the decision moment; write-back under grant).
4. **Trust/regulatory** — consent receipts, revocation-on-read (already skeletoned), de-identification
   for opt-in commons, SaMD boundary controls, the non-diagnostic guardrail as an enforced invariant.

Everything is modular so a real feed — open (LOINC, RxNorm, CVX, USCDI value sets, OpenStax anatomy) or
paid (a QHIN membership, a lab network) or patient-authorized (the person's own OAuth grant) — drops
into a connector's `fetch` without touching `normalize` or anything downstream.

### Wall 2 — reconciliation & extraction: reuse the estate, don't rebuild it
The twin is an **orchestrator**, not a new NLP/ER/vector stack. Wall 2 delegates entirely to services
that already exist and ship in `prophet-platform/apps/` (`src/reconcile/`):

| Need | Estate service (reused) | Endpoint | What the twin does with it |
|---|---|---|---|
| **Cross-source dedup / golden records** | `entity-resolution` | `POST /resolve` | Feed ingested records (name + coded attributes) → **proof-carrying** golden records + a replayable decision ledger. Each golden record is annotated with the union of contributing sources. |
| **Unstructured → facts** | `ie-engine` (spaCy) | `POST /extract` | C-CDA narrative / discharge summary / OCR'd PDF → candidate entities + claims, surfaced at **tier=hypothesis** (never promoted without clinician attestation). |
| **Verify generated claims** | `holmes` | `POST /verify` | Any summary the twin generates has its claims verified against HellGraph — the **anti-Watson guard** (no assertion sold as truth without grounding). |
| **Semantic search over records** | `hellgraph-service` | `POST /api/graph/node`, `GET /api/graph/ground` | Land records as typed nodes, then hybrid **HNSW⊕BM25 RRF** cited retrieval. |
| **Entailments / promotion** | `owl-reasoner` | `POST /reason` | Reason over the twin's `twin.ttl` → RDFS/OWL-RL closure (conditions ⊑ `hdt:FHIRResource`, drives correspondence promotion). |
| **Vectors** | `embeddings` | `POST /v1/embeddings` | 768-dim nomic vectors (L2-normalized, cosine=dot) for direct analyte-similarity when needed. |

Every reconcile route **degrades gracefully**: a down service reports `degraded` and the twin keeps
working (local-first) — a dependency is never a hard requirement. **Proven live end-to-end:** with
`entity-resolution` running, ingesting Epic + Blue Button + Apple and calling `POST
/api/health/reconcile` deduped 13 records → 12 golden, merging *Lisinopril* across Epic (a
`MedicationRequest`) and Blue Button (a Part D fill) into one record with a replayable
`MERGE_VERIFIED` decision (name_sim 1.0, attr_sim 1.0) and both sources credited — the aggregator
"90% dedup" feature, but **auditable** and built on estate primitives, not a homegrown matcher.
