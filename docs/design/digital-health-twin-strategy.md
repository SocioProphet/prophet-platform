# Digital Health Twin — product & market strategy

> Companion to `digital-health-twin.md` (design) and `digital-health-twin-feature-atlas.md` (the feature
> superset). Status: STRATEGY CAPTURE, 2026-07-21. Non-diagnostic PHR posture; sovereign + AI-first.

## Thesis (one line)
**Your body, sovereign and legible** — the one place that holds your whole health record (which *you*
own), rendered as an anatomical twin, reasoned over by an ontology, holding modern *and* traditional
lenses honestly, and readable by the people/agents you grant under revocable, receipted consent.
Anti-Epic **and** anti-woo. The differentiator no incumbent holds is the **combination** of five things.

## The five-part moat (what nobody combines)
1. **Patient-sovereign lifetime record** — you own it, local-first, export-and-leave.
2. **Anatomical twin as the interface** — a body you look *into*, records painted on the anatomy.
3. **Ontology-typed reasoning** — facts type into the HDT ontology (`socioprophet.md/ont/health#`) and
   entail (verified: twin.ttl + TBox → +537 inferred triples).
4. **The honest epistemic bridge** — modern neuroanatomy (verified) + chiropractic/TCM/reflexology
   (traditional, attributed) + bridge claims (hypothesis) on one body, tiered, evidence-driven.
5. **Cryptographic governed consent** — grant → receipt → revoke → read-blocked. Consent is the moat
   *and* the business model (a consent economy, not extraction).

## Competitive landscape — pieces exist, the combination doesn't
| Segment | Leaders | What they lack vs. us |
|---|---|---|
| Patient record aggregation | **Apple Health Records** (SMART-on-FHIR, 800+ systems, on-device) · Google Health Connect | Ecosystem-locked, no reasoning, no true sovereignty, no bridge, not a twin |
| Provider portal | **Epic MyChart** | Provider-owned, siloed per system, not patient-sovereign |
| Data plumbing (B2B) | **Health Gorilla** (QHIN) · Particle · 1up · b.well · **Metriport** (OSS) · Seqster · PicnicHealth | Infrastructure, not a consumer twin |
| Nonprofit PHR | **CommonHealth** (The Commons Project) | Android-only, no twin/reasoning |
| Physiological twin | **Q Bio** (whole-body MRI) · **Twin Health** (metabolic) · Unlearn.ai (trials) | Scan/disease-specific, not sovereign, not records-first, no bridge |
| 3D anatomy | **BioDigital Human** · Complete Anatomy · Z-Anatomy (OSS) | Generic anatomy, not *your* data |
| Clinical AI | Med-PaLM/MedLM · Hippocratic · Abridge · Nuance DAX | Documentation/Q&A, not a sovereign record twin |
| Knowledge graphs | SNOMED · UMLS · PrimeKG · Hetionet | Substrate, not a product |
| Integrative/longevity | Parsley/Function/Superpower/Levels | Assert the bridge as fact or ignore it; no sovereign twin |

**Graveyard (why this is hard):** Microsoft HealthVault (dead 2019), Google Health (dead ×2), IBM
Watson Health (sold for parts). Consumer PHRs + health-AI die from: data-access chicken-egg, trust,
no reimbursement, and clinician workflow. Our answer to the graveyard is the sovereign consent-economy
model (below) — not a feature, a different market structure.

## Gap register — prototype → product
- **Real ingestion** (THE game): SMART-on-FHIR provider connectors, Apple/Google Health import, DICOM,
  OCR of scanned records/PDFs.
- **Local-first encrypted store** on a real device/node (today: in-memory synthetic).
- **Verified identity + recovery** without a central custodian.
- **Clinical correctness**: maintained LOINC/SNOMED/RxNorm maps, UCUM units, age/sex reference ranges,
  drug-interaction + care-gap content (sourced + validated).
- **Regulatory**: HIPAA posture, SOC 2 / HITRUST; **FDA SaMD** analysis for any prediction/CDS feature
  (the correspondence + x(t) model is the risk); keep insights "informational/wellness" until cleared.
- **Interop certification**: ONC/USCDI; **TEFCA/QHIN**, Carequality, CommonWell (partner or become one).
- **Production provenance**: tamper-evident, legally-admissible audit (receipts are the primitive).
- **Visual**: real DICOM viewer, the 3D model, the likeness.
- **Multi-party workflows**: referral / second-opinion / care-team, with the counterpart's UI.

## Multi-sided go-to-market (health is a multi-sided market)
Sovereignty is both the differentiator **and** the wedge: patient consent unlocks data providers and
insurers can't easily get.

- **People (substrate + wedge).** Not "a PHR for everyone" (the graveyard). A **high-need beachhead**:
  chronic/complex patients juggling many providers · caregivers managing a parent · quantified-self /
  longevity (wearables + the bridge) · a condition community (diabetes, autoimmune). Value: whole record
  you own · a twin that reasons · share on your terms. Free + sovereign; monetize agents/provider/payer.
- **Providers.** Pain: they see only their own silo. We give a **complete, patient-consented longitudinal
  record**, pre-visit summaries, less chart-chasing. The grant→receipt→revoke primitive *is* provider
  access. Ship as a **SMART-on-FHIR app launched inside Epic/Cerner**. Model: per-seat / per-encounter /
  value-based (readmission reduction).
- **Payers/employers.** Value: consented risk stratification, **care-gap closure** (HEDIS/STAR), reduced
  duplicate testing, **HCC/risk-adjustment coding accuracy** (SNOMED/ICD-typed records help directly),
  prior-auth streamlining. Model: PMPM / value-based. Guardrail: **GINA/ACA** anti-discrimination — the
  sovereign consent model is the ethics (patient grants revocably and is paid; the payer never extracts).

## The connective thesis — a consent economy
The patient owns the record; **consent is the currency**; value flows *back* to the patient (a
data-dividend). The estate already has the primitives: the **Memory Distribution Grant**, the
**Capability Membrane**, reciprocal-channel governance, the sovereignty doctrine. Not "we extract your
health data" — "you own it, agents reason on it under your grant, and every party pays *you* for access."

## Sequencing
1. **Real consumer ingestion** (Apple Health + 2–3 SMART-on-FHIR + DICOM/manual) on the local-first store
   — a genuinely useful sovereign PHR for a beachhead cohort.
2. **The governed consent/agent layer** as the visible differentiator.
3. **One provider pilot** (SMART-on-FHIR app) proving "complete consented record" value.
4. **One payer/employer pilot** on consented, de-identified population signal + care-gap closure.
5. **Reasoning / twin / bridge** = retention + moat, NOT the wedge (what makes people stay + can't be
   copied; not what gets them in the door).
6. **Regulatory in lockstep**: consumer-PHR (light) → SOC2/HITRUST + TEFCA for exchange → FDA analysis
   before any prediction/CDS ships as more than informational.

## Verified market survey (2026) — grounded competitor intelligence
*A 13-vendor web survey; specifics cited to vendor docs/press. Key strategic signals flagged 🔴.*

**Patient PHR / aggregation**
- **Apple Health Records** — SMART-on-FHIR from 800+ systems; 7 clinical categories; on-device + E2E iCloud sync; Medications w/ interaction warnings; full Watch sensor suite (ECG, AFib, SpO2, VO2max, sleep); HealthKit/ResearchKit/CareKit SDKs; XML export. **iOS-only; US/UK/CA records; read-only; Share-with-Provider US-only.**
- **Google Health Connect** — Android on-device plumbing, 61 data types, granular per-type permissions; **not a PHR** (no EHR aggregation; nascent FHIR Medical Records API).
- **CommonHealth** — Android PHR filling Apple's gap; SMART-on-FHIR + SMART Health Cards; on-device; **Apache-2.0 open SDK**; 700+ sources.
- **Epic MyChart** — dominant but **per-org toggled**; Share Everywhere (one-time 60-min code, no account); Happy Together (cross-org aggregation, weak for non-Epic); Care Companion RPM (150+ care plans); **Lucy PHR retired 12/31/2025**; messaging now sometimes billed.

**Data aggregators (B2B)** — Health Gorilla (**QHIN + QHIO**, Patient360 retrieve/normalize/dedup, 120+ lab network, HITRUST); b.well (white-label SDKs incl. a **Health SDK for AI/LLM**, TEFCA, **CLEAR IAL2 identity**, **OpenAI "ChatGPT Health" data partner**); 1upHealth (payer-focused, **sunsetting patient-mediated Patient Connect Sept 30 2026**); Particle Health (Carequality); **Metriport** (genuinely **open-source AGPLv3 + self-hostable** — the one we'd fork/vendor; rides CommonWell+Carequality, not a QHIN, abandoned wearables); **PicnicHealth** (patient-mediated *concierge* retrieval — pulls records for you via HIPAA authorization, no portal logins; proprietary **LLMD** medical model; monetizes de-identified RWD to pharma); **Seqster** (multi-modal EHR + genomic/DNA + wearables + **family/pedigree** records, white-label, pivoted to pharma RWD); wearable aggregators Terra/ROOK/Thryve (400–500+ devices).

**🔴 SIGNAL — interoperability access is legally contested, and our model is the clean path.** Epic filed a Carequality dispute and **cut off Particle Health** (2024) over "Treatment"-purpose abuse + a ~70:1 reciprocity imbalance; Particle's **antitrust suit against Epic survived dismissal (Sherman §2, Sept 2025, now in discovery)**; an **Epic v. Health Gorilla** dispute is live (2026). Two Particle customers were suspended — one for helping patients get *their own* records under a mis-used "treatment" purpose. **The sanctioned patient-pull path is TEFCA Individual Access Services (IAS) with IAL2 identity + explicit consent — which is exactly our sovereign/consent model.** Our wedge is legally *advantaged* over the treatment-purpose aggregators getting litigated.

**Standards (the ingest surface):** SMART-on-FHIR (patient + EHR launch, `offline_access` background sync, write-back scopes); **USCDI v6 = 22 data classes** (our canonical twin schema; incl. Provenance + SDOH); **11 designated QHINs**; **Blue Button 2.0** (Medicare claims, 60M+ beneficiaries, EOB/Coverage); **SMART Health Cards/Links** (patient-held, signed, offline-verifiable, passcode+expiry — a perfect fit for our sovereign revocable consent); DICOMweb (WADO/QIDO/STOW-RS); CDS Hooks (push twin intelligence into the EHR at the decision moment).

**Digital twins** — Q Bio (descriptive longitudinal, whole-body MRI, **single CA location**); Twin Health (metabolic reversal, **RCT-backed**, B2B2C employer/plan); Unlearn.ai (trial control-arm twins, **EMA/FDA-qualified**); Dassault Living Heart (mechanistic FE sim, FDA regulatory-science, not patient-facing); Siemens (cardiac twin, pilot-stage); Philips (data plane, twin aspirational). **🔴 SIGNAL: every one is enterprise/clinician/regulator-facing — none is patient-owned, sovereign, or continuously-updating. Confirmed white space.**

**3D anatomy** — BioDigital (API/embed leader, 14k structures, conditions now paywalled); Complete Anatomy (deep dissection/tracer tools, beating heart, **no public API**); **Z-Anatomy (CC-BY-SA, open, 7k structures, TA2 — our 3D substrate)**; Visible Body. **🔴 SIGNAL: NONE personalize to a real patient's imaging/data. Confirmed opportunity — the personalized twin is open.**

**Clinical AI** — Med-PaLM/MedLM (cloud/Vertex; **MedGemma open, single-GPU, on-device-capable** — the sovereign-AI substrate); Hippocratic (voice "AI nurses", non-diagnostic, cloud/NVIDIA); **Abridge** (ambient + **Linked Evidence** traceability + **real-time ICD-10/HCC/CPT coding**, $5.3B); Microsoft Dragon/DAX Copilot (Epic-embedded); **OpenEvidence** (free NPI-verified Q&A, **licensed NEJM+JAMA corpus**, **Coding Intelligence**, $12B Jan 2026); Glass Health (3-tier DDx + A&P); UpToDate (GRADE + Lexidrug + Expert AI). **🔴 SIGNALS: (a) coding intelligence (ICD/HCC/CPT) is the hot monetizable feature → our payer/provider revenue; (b) citation-grounding is now table stakes — our epistemic-tiered, proof-carrying reasoning goes beyond it; (c) on-device (MedGemma-class) is the sovereign wedge vs cloud-tethered incumbents.**

**Longevity/labs (our beachhead cohort)** — Function ($365/yr, 160+ tests + **$499 Ezra full-body MRI**); Superpower ($199/yr, 100+ biomarkers, bio-age); InsideTracker (48 blood + 261 DNA variants); Levels (CGM + metabolic score). **🔴 SIGNAL: high willingness-to-pay, wearables-native, data-hungry — and none is sovereign or a real reasoned twin. This is the wedge cohort.**

## "Bury them" = integrate the superset
The plan is not to out-feature one competitor; it's to **integrate what's scattered across all of them**
(Apple = aggregation, Twin Health = physiology, BioDigital = anatomy, Health Gorilla = plumbing, the
integrative world = the bridge) into one sovereign, AI-first, ontology-reasoned product. The exhaustive
capability set we're building toward is the **feature atlas** (`digital-health-twin-feature-atlas.md`),
each feature tagged with competitor coverage, our sovereign/AI-first approach, and a build tier.
