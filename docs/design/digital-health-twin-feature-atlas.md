# Digital Health Twin — feature atlas (the superset to build)

> The exhaustive capability set for the sovereign, AI-first health twin — everything scattered across
> Apple Health, Epic MyChart, Health Gorilla, Q Bio, Twin Health, BioDigital, Metriport, the integrative
> world, and the standards bodies, integrated into ONE product. Companion to
> `digital-health-twin-strategy.md`. Status: capture 2026-07-21. ~500 features across 22 domains.
>
> **Tiers:** `[0]` wedge / must-have · `[1]` core product · `[2]` differentiator / moat · `[3]` advanced.
> **✦** = where our sovereign + AI-first thesis specifically beats the incumbent. Non-diagnostic PHR posture throughout.

---

## 1 · Record ingestion & connectors
*Edge ✦: aggregate from every source but land it on the person's own node, not a vendor cloud.*
1. SMART-on-FHIR patient-access connector (individual provider) `[0]`
2. Bulk connect: search + link many providers at once (à la Apple Health Records, 800+ systems) `[0]`
3. TEFCA / QHIN network retrieval (via partner or become a QHIN) `[1]`
4. Carequality + CommonWell query `[1]`
5. Apple Health / HealthKit import `[0]`
6. Google Health Connect import `[1]`
7. CMS Blue Button 2.0 (Medicare claims) `[1]`
8. Payer patient-access API (CMS Interoperability rule) `[1]`
9. C-CDA / CCD document import `[1]`
10. DICOM / DICOMweb imaging import `[0]`
11. PDF / scanned-record OCR ingest (extractive) `[0]`
12. Photo capture of paper records → structured `[1]`
13. Lab portal connectors (LabCorp, Quest) `[0]`
14. Pharmacy connectors (Surescripts medication history) `[1]`
15. Immunization registry (IIS) pull `[2]`
16. e-mail / fax inbound record intake `[2]`
17. Manual entry (any record type) `[0]`
18. SMART Health Cards / SMART Health Links import `[1]`
19. HL7v2 feed ingest (institutional) `[2]`
20. FHIR Bulk Data ($export) for population/self `[2]`
21. Wearable/device connectors (see §6) `[0]`
22. Genomics report import (VCF, 23andMe/Ancestry export) `[2]`
23. Continuous sync + delta updates from linked sources `[1]`
24. De-duplication + record reconciliation across sources ✦`[1]`
25. Source provenance stamped on every imported fact ✦`[0]`
26. Connector health dashboard (what's linked, last sync, gaps) `[1]`
27. Offline / airplane ingest queue (local-first) ✦`[2]`
28. Family/dependent record intake (pediatric, elder) `[1]`
29. Historical backfill (pull full history, not just recent) `[1]`
30. Import audit (what came in, when, from where) `[1]`

## 2 · Clinical record data types (USCDI-complete)
*Edge ✦: every class typed to the HDT ontology (SNOMED/LOINC/RxNorm/ICD) — not flat text.*
31. Problems / conditions (SNOMED/ICD) `[0]`
32. Medications (RxNorm) + medication statements `[0]`
33. Allergies & intolerances `[0]`
34. Immunizations (CVX) `[0]`
35. Lab results (LOINC) `[0]`
36. Vital signs `[0]`
37. Procedures (CPT/SNOMED) `[1]`
38. Encounters / visits `[0]`
39. Clinical notes (all note types) `[1]`
40. Diagnostic reports `[1]`
41. Care team members `[1]`
42. Care plans & goals `[1]`
43. Health concerns `[2]`
44. Social history / SDOH `[2]`
45. Smoking status `[2]`
46. Functional & disability status `[2]`
47. Mental / cognitive status `[2]`
48. Unique device identifiers (implants) `[2]`
49. Pregnancy status & history `[1]`
50. Family history / pedigree `[1]`
51. Advance directives / living will `[2]`
52. Patient demographics + identifiers `[0]`
53. Provenance resource per record ✦`[0]`
54. Encounters → diagnoses → orders linkage `[1]`
55. Specimen / pathology `[2]`
56. Observations beyond labs (assessments, scores) `[1]`
57. Questionnaire responses (PROs/PROMs) `[2]`
58. Referrals / service requests `[1]`
59. Coverage / insurance records `[1]`
60. Billing / claims (EOBs) `[1]`
61. Consent records as first-class data ✦`[0]`
62. Body-site / laterality coding (localizedTo) ✦`[1]`
63. Nutrition / diet orders `[3]`
64. Adverse event / safety reports `[2]`

## 3 · Imaging & DICOM
*Edge ✦: your imaging is yours — offline viewer, not a hospital PACS you can't leave with.*
65. DICOM import (X-ray, CT, MRI, US, mammo, PET) `[0]`
66. In-browser DICOM viewer (cornerstone-class) `[1]`
67. Offline / local viewing ✦`[1]`
68. Multi-frame / series scrubbing `[1]`
69. Window/level, zoom, pan, measure `[1]`
70. MPR (multiplanar reconstruction) `[2]`
71. 3D volume rendering `[3]`
72. Study/series/instance hierarchy browse `[1]`
73. Report ↔ image linkage `[1]`
74. Prior-study comparison `[2]`
75. Image annotations (yours, shareable) `[2]`
76. AI findings overlay (informational, cited) ✦`[2]`
77. Localize imaging to organ on the twin ✦`[2]`
78. Radiology report structured extraction `[2]`
79. Export/share imaging under grant ✦`[1]`
80. Ophthalmology / derm / endoscopy image types `[3]`
81. ECG / waveform viewing `[2]`
82. Pathology whole-slide (WSI) `[3]`
83. Imaging de-identification for sharing `[2]`
84. Imaging storage on local node ✦`[1]`

## 4 · Labs & biomarkers
*Edge ✦: trends + reference-range reasoning across a lifetime, from any lab, unified.*
85. Lab result trends (per analyte, over time) `[0]`
86. Reference-range flags (age/sex-aware) `[1]`
87. Out-of-range highlighting `[0]`
88. Unit normalization (UCUM) ✦`[0]`
89. Cross-lab harmonization (LabCorp vs Quest) ✦`[1]`
90. Panels grouped (CBC, CMP, lipid, thyroid, A1c) `[0]`
91. Biomarker "optimal vs normal" ranges (longevity) `[2]`
92. Full biomarker panels (Function/Superpower-class, 100+ markers) `[2]`
93. Sparkline per marker inline ✦`[1]`
94. Delta since last result `[1]`
95. Correlated-marker clustering (cardiometabolic, etc.) ✦`[2]`
96. Lab-to-condition linkage `[1]`
97. Continuous glucose (CGM) integration (Levels/Dexcom) `[2]`
98. Continuous biomarker streams `[3]`
99. Home-test / at-home kit intake `[2]`
100. Result explanation (plain-language, cited, non-dx) ✦`[1]`
101. Trend-based alerts (informational) `[2]`
102. Population percentile (consented, de-identified) ✦`[3]`
103. Lab ordering (provider-side / partner) `[3]`
104. Genomic-informed lab interpretation `[3]`
105. Fasting/context tagging on results `[2]`
106. Menstrual-cycle-aware ranges `[2]`
107. Pediatric growth-percentile ranges `[2]`
108. Biomarker "what changed + why" narrative ✦`[2]`
109. Export lab history (CSV/FHIR) ✦`[1]`

## 5 · Medications & pharmacy
110. Active medication list `[0]`
111. Medication history (Surescripts) `[1]`
112. Dosage / frequency / route `[0]`
113. Drug–drug interaction check (informational) `[2]`
114. Drug–allergy check `[2]`
115. Drug–condition contraindication (informational) `[2]`
116. Adherence tracking / reminders `[2]`
117. Refill status + pharmacy `[1]`
118. Medication timeline (started/stopped) `[1]`
119. Prescriber linkage `[1]`
120. RxNorm normalization ✦`[0]`
121. Supplement / OTC tracking `[2]`
122. Deprescribing insight (informational) `[3]`
123. Pharmacogenomics (PGx) flags `[3]`
124. Cost / formulary lookup `[3]`
125. Medication reconciliation across sources ✦`[1]`
126. Localize medication effect to organ/system ✦`[3]`

## 6 · Wearables & sensors
*Edge ✦: unify every stream on-device; the person owns the raw signal, not the vendor.*
127. Apple Watch (HR, HRV, ECG, SpO2, AFib, sleep, activity, VO2max, temp) `[0]`
128. Fitbit / Google (steps, HR, sleep, SpO2) `[1]`
129. Oura ring (sleep, HRV, temp, readiness) `[1]`
130. Garmin (activity, HRV, stress, pulse ox) `[1]`
131. Dexcom / Abbott CGM (glucose) `[2]`
132. Withings (BP, weight, sleep, ECG) `[1]`
133. Blood-pressure cuffs `[1]`
134. Smart scale (weight, body comp) `[1]`
135. Pulse oximeter `[2]`
136. Sleep trackers `[1]`
137. Continuous HR / HRV `[1]`
138. Respiratory rate `[2]`
139. Skin temperature `[2]`
140. Activity / steps / exercise `[0]`
141. VO2 max / cardio fitness `[2]`
142. Menstrual / fertility tracking `[2]`
143. Mood / mental-health check-ins `[2]`
144. Environmental (air quality, UV) `[3]`
145. Raw-signal retention on node ✦`[3]`
146. Wearable → vital-sign FHIR mapping `[1]`
147. Anomaly detection on streams (informational) ✦`[2]`
148. Wearable data → body-state x(t) input ✦`[2]`
149. Cross-device conflict resolution ✦`[2]`
150. Continuous vitals timeline `[2]`

## 7 · Genomics & multi-omics
151. Genomic report import (VCF) `[2]`
152. Consumer-DNA import (23andMe/Ancestry) `[2]`
153. Pharmacogenomics (PGx) `[3]`
154. Polygenic risk scores (informational) `[3]`
155. Rare-disease variant flags (HPO/MONDO) `[3]`
156. Carrier status `[3]`
157. Ancestry / trait reports `[3]`
158. Microbiome import `[3]`
159. Proteomics / metabolomics `[3]`
160. Genomic privacy vault (extra-guarded, GINA) ✦`[2]`
161. Variant → condition ontology linkage `[3]`
162. Family pedigree + inheritance `[3]`
163. Genome-informed lab/med interpretation `[3]`
164. Epigenetic / biological-age clocks `[3]`
165. Consent-scoped genomic sharing ✦`[2]`

## 8 · The anatomical twin (visual model)
*Edge ✦: a body that looks like YOU, with YOUR data painted on it — nobody personalizes anatomy.*
166. Organ-system index (the anatomical diagram as navigation) `[0]`
167. Polished per-system illustrations (CC-BY OpenStax/Servier) `[0]`
168. Records painted onto organs (localizedTo) ✦`[1]`
169. Epistemic coloring on the body (verified/traditional/hypothesis) ✦`[2]`
170. Clickable organs → records `[0]`
171. 3D rigged body (Z-Anatomy / three.js) `[2]`
172. Layer toggles (skeletal/muscular/cardio/nervous/…) `[2]`
173. Rotate / zoom / peel systems `[2]`
174. Personalized body shape (from metrics) ✦`[2]`
175. Skin-tone / body-type selection ✦`[2]`
176. Optional face/likeness (opt-in) ✦`[3]`
177. Sex-specific anatomy `[1]`
178. Pediatric anatomy scaling `[3]`
179. Condition overlays (where it manifests) ✦`[2]`
180. Imaging localized on the 3D body ✦`[3]`
181. Spinal correspondence chart (three lenses) ✦`[2]`
182. Dermatome / myotome maps `[2]`
183. Autonomic innervation map `[2]`
184. Vascular / lymphatic overlays `[3]`
185. Time-lapse: the twin over your life ✦`[3]`
186. AR / spatial view (Vision Pro / mobile AR) `[3]`
187. Print / export the twin `[3]`
188. Accessibility (screen-reader anatomy) `[1]`
189. Meridian / reflexology overlays (labeled tradition) ✦`[2]`
190. "Show me where X is / does" guided anatomy ✦`[2]`

## 9 · Reasoning & twin intelligence (AI-first)
*Edge ✦: ontology-typed, proof-carrying, epistemic-labeled reasoning — cited, never a black box.*
191. Ontology-typed facts (SNOMED/LOINC/RxNorm/health:) ✦`[0]`
192. OWL/RDFS reasoning over the twin (owl-reasoner) ✦`[1]`
193. Cross-system correlation surfacing (informational) ✦`[2]`
194. Plain-language record summarization (extractive, cited) ✦`[1]`
195. "Explain this result / condition / med" (cited, non-dx) ✦`[1]`
196. Timeline narrative ("what happened, when") ✦`[1]`
197. Care-gap detection (screenings due) `[2]`
198. Trend/anomaly insight (informational) `[2]`
199. Question-answering over your record (RAG, cited) ✦`[1]`
200. Pre-visit summary generation ✦`[1]`
201. Second-opinion agent (governed) ✦`[2]`
202. Longitudinal-trend agent `[2]`
203. Drug-interaction reasoning `[2]`
204. Differential-context (informational, never diagnostic) ✦`[3]`
205. Epistemic tiering on every inference ✦`[2]`
206. Proof / provenance for every AI claim ✦`[1]`
207. Attested (deterministic) vs generative summaries labeled ✦`[1]`
208. Guideline-grounded reasoning (USPSTF/specialty) `[2]`
209. Multi-lingual explanations `[2]`
210. Health-literacy-adaptive language ✦`[2]`
211. "What should I ask my doctor?" prep ✦`[2]`
212. Symptom-to-record correlation (informational) `[3]`
213. Body-state prediction (x(t), guarded) ✦`[3]`
214. Correspondence promotion via evidence (membrane) ✦`[2]`
215. Local / on-device inference option (sovereign) ✦`[2]`
216. Agent tool-use over the record (governed) ✦`[2]`
217. Reasoning replay / audit ✦`[2]`
218. Confidence + uncertainty surfaced ✦`[2]`
219. Contradiction detection across sources ✦`[2]`
220. Reference/citation panel on every insight ✦`[1]`

## 10 · The correspondence bridge (ancient ↔ modern)
*Edge ✦: the genuine white space — held honestly, tiered, evidence-driven. Nobody else does this.*
221. Modern neuroanatomy layer (verified) `[2]`
222. Chiropractic meric chart (traditional, attributed) `[2]`
223. TCM meridian system (attributed) `[2]`
224. Reflexology zones (attributed) `[3]`
225. Ayurvedic chakra/nadi (attributed) `[3]`
226. Bridge claims (hypothesis, with evidence) ✦`[2]`
227. Epistemic tier per correspondence ✦`[2]`
228. Provenance per traditional mapping ✦`[2]`
229. Supporting / refuting evidence attached ✦`[2]`
230. Promotion / demotion by evidence (membrane) ✦`[3]`
231. Non-diagnostic framing enforced ✦`[0]`
232. Toggle lenses on the body ✦`[2]`
233. "Same point, three lenses" comparison ✦`[2]`
234. Traditional-practitioner view (opt-in) `[3]`
235. Fascia / connective-tissue research layer `[3]`
236. Referred-pain / viscerosomatic map (verified) `[2]`
237. Cross-tradition concordance analysis ✦`[3]`
238. Cite the tradition's source text ✦`[3]`
239. User-contributed correspondences (governed, tiered) `[3]`
240. Bridge-claim research feed `[3]`

## 11 · Timeline & longitudinal record
241. Unified lifetime timeline `[0]`
242. Encounter timeline (gantt-style) `[1]`
243. Filter by system / organ / type `[1]`
244. Episodes of care grouping `[2]`
245. Milestone markers (dx, surgery, etc.) `[1]`
246. Care-pathway lineage (referral→test→dx→tx) ✦`[2]`
247. Zoomable (day → decade) `[1]`
248. Search across the whole record ✦`[0]`
249. "On this day" / anniversaries `[3]`
250. Trend overlays on timeline `[2]`
251. Life-event context (pregnancy, injury) `[2]`
252. Export timeline `[1]`

## 12 · Consent, sharing & governance (the moat)
*Edge ✦: cryptographic, revocable, receipted — a consent ECONOMY, not a TOS checkbox.*
253. Scoped grant (system / date / code-system / record) ✦`[0]`
254. Time-boxed grants (TTL) ✦`[0]`
255. Receipt on every access ✦`[0]`
256. Read-enforced revocation ✦`[0]`
257. Grant to a person (clinician, family) `[0]`
258. Grant to an agent ✦`[1]`
259. Grant ledger + audit view `[0]`
260. Break-glass emergency access (logged) `[2]`
261. Proxy / caregiver / guardian access `[1]`
262. Minor / dependent consent rules `[2]`
263. Purpose-of-use tagging on grants ✦`[2]`
264. One-time vs standing grants `[1]`
265. SMART Health Links share `[1]`
266. QR / link share (scoped) `[1]`
267. Revoke everything (kill switch) ✦`[1]`
268. Consent for research (separate, opt-in) ✦`[2]`
269. De-identified vs identified sharing toggle ✦`[2]`
270. Data-dividend / paid-consent rails ✦`[3]`
271. Consent receipts exportable / portable ✦`[2]`
272. Third-party access notifications `[1]`
273. Granular field-level redaction ✦`[2]`
274. Consent expiry reminders `[2]`
275. Capability-membrane gating (estate primitive) ✦`[2]`
276. Memory-distribution-grant integration ✦`[2]`
277. Access-pattern anomaly alerts ✦`[2]`
278. Shared-with-me inverse view (as a clinician) `[2]`
279. Consent for agent tool-use, per tool ✦`[2]`
280. Legal-hold / litigation export `[3]`

## 13 · Identity, auth & recovery
281. Sovereign identity (self-custody) ✦`[1]`
282. Passkey / WebAuthn login `[0]`
283. Device binding `[1]`
284. Social / delegated recovery (no central custodian) ✦`[2]`
285. Biometric unlock `[1]`
286. Multi-device sync with E2E keys ✦`[2]`
287. Identity verification (for provider trust) `[2]`
288. Patient matching (across sources) `[1]`
289. Verifiable credentials (VC) for identity ✦`[3]`
290. Guardian / estate succession (who inherits) ✦`[3]`
291. Pseudonymous mode `[3]`
292. Account portability / export-and-leave ✦`[1]`

## 14 · Storage, sovereignty & sync
*Edge ✦: local-first, encrypted, on YOUR node — the whole thesis.*
293. Local-first encrypted store `[0]`
294. On-device (phone/laptop) primary `[1]`
295. Sovereign-node / BearBrowser sidecar `[2]`
296. Content-addressed, hash-sealed media ✦`[1]`
297. Encrypted backup (user-held keys) `[1]`
298. Multi-node sync (CRDT/Autobase) ✦`[2]`
299. Offline-first operation `[1]`
300. Selective sync (which data where) `[2]`
301. Export full archive (FHIR bundle + media) ✦`[0]`
302. Import from export (portability) `[1]`
303. Zero-knowledge storage option ✦`[2]`
304. Bring-your-own-storage (S3/IPFS/personal) ✦`[3]`
305. Versioned / immutable record history ✦`[2]`
306. Tamper-evidence on the store ✦`[2]`
307. Storage-quota + media management `[2]`
308. Cross-platform (iOS/Android/desktop/web) `[1]`
309. Family shared vault (governed) `[2]`
310. Node health / integrity checks `[2]`
311. Disaster recovery / redundancy `[2]`
312. Data-residency choice (jurisdiction) ✦`[3]`

## 15 · Privacy, security & compliance
313. HIPAA-aligned posture `[0]`
314. SOC 2 / HITRUST `[1]`
315. End-to-end encryption ✦`[1]`
316. Encryption at rest + in transit `[0]`
317. Audit logging (immutable) ✦`[1]`
318. De-identification pipeline (Safe Harbor / Expert) `[2]`
319. GDPR rights (access/portability/erasure) ✦`[1]`
320. Right-to-delete (real, sovereign) ✦`[1]`
321. GINA / ACA anti-discrimination guardrails ✦`[2]`
322. Consent-first data flows ✦`[0]`
323. Breach detection + notification `[2]`
324. Pen-test / security review cadence `[2]`
325. PHI minimization by default ✦`[1]`
326. Non-diagnostic guardrail enforcement ✦`[0]`
327. FDA SaMD boundary controls ✦`[1]`
328. Data-processing transparency / receipts ✦`[1]`
329. No-vendor-cloud-by-default ✦`[1]`
330. Secure enclave / TEE for keys `[3]`
331. Compliance reporting (for B2B) `[2]`
332. Children's privacy (COPPA) `[2]`

## 16 · Provider-facing
*Edge ✦: give the clinician the COMPLETE consented record they never had.*
333. SMART-on-FHIR app launched in Epic/Cerner `[1]`
334. Complete consented longitudinal record view ✦`[1]`
335. Pre-visit patient summary ✦`[1]`
336. Reconciled med/allergy/problem list ✦`[1]`
337. Outside-records aggregation (Happy Together+) `[2]`
338. Care-gap flags at point of care `[2]`
339. CDS Hooks integration `[2]`
340. Referral / second-opinion inbound `[2]`
341. Patient-generated-data review (wearables) `[2]`
342. Structured message to patient `[2]`
343. Order / result write-back (governed) `[3]`
344. Clinician annotations on the twin `[3]`
345. Consent request flow (ask patient for access) ✦`[2]`
346. Time-limited chart access ✦`[1]`
347. Specialty views (cardiology, endo, etc.) `[3]`
348. Documentation assist (ambient, cited) `[3]`
349. Coding suggestion (ICD/CPT, informational) `[3]`
350. Care-team roster + roles `[2]`
351. Provider directory / find-a-doc `[3]`
352. Telehealth context handoff `[3]`
353. Discharge-summary reconciliation `[2]`
354. Provider audit of their own access ✦`[2]`

## 17 · Payer / employer-facing
*Edge ✦: consented population signal — the patient is paid, never extracted from.*
355. Consented risk stratification `[2]`
356. HCC / risk-adjustment coding support ✦`[2]`
357. HEDIS / STAR care-gap closure `[2]`
358. Population-health analytics (de-identified) `[2]`
359. Prior-authorization automation `[3]`
360. Member engagement / activation `[2]`
361. SDOH insight `[3]`
362. Value-based-care measurement `[2]`
363. Duplicate-test avoidance ✦`[2]`
364. Cohort building (consented) `[3]`
365. Real-world-evidence contribution (opt-in) ✦`[3]`
366. Employer wellness integration `[3]`
367. Benefit / formulary surfacing to member `[3]`
368. Claims ↔ clinical reconciliation `[3]`
369. Consent-economy payment rails ✦`[3]`
370. Anti-discrimination audit (GINA) ✦`[2]`
371. Actuarial signal (aggregate, consented) `[3]`
372. Quality-measure reporting `[2]`
373. Chronic-care-management enrollment `[3]`
374. Prevention-program targeting (consented) `[3]`

## 18 · Care coordination & workflows
375. Care team directory `[1]`
376. Appointment tracking / scheduling `[2]`
377. Referral management `[2]`
378. Task / to-do (follow-ups, refills) `[2]`
379. Care plan tracking `[2]`
380. Reminders (screenings, meds, appts) `[2]`
381. Secure messaging (patient↔care team) `[2]`
382. Second-opinion request flow `[2]`
383. Family / caregiver coordination `[2]`
384. Emergency card / Medical ID `[1]`
385. Advance-directive sharing `[2]`
386. Transition-of-care summaries `[2]`
387. Symptom / journal logging `[2]`
388. Shared decision-making tools `[3]`
389. Goal setting + progress `[2]`

## 19 · Preventive, longevity & wellness
390. Screening schedule (USPSTF, age/sex) `[2]`
391. Immunization due/overdue `[1]`
392. Risk calculators (ASCVD, FRAX, etc., informational) `[2]`
393. Biological-age / longevity metrics `[3]`
394. Optimal-range biomarker targets `[2]`
395. Nutrition / diet tracking `[3]`
396. Fitness / activity goals `[2]`
397. Sleep insight `[2]`
398. Stress / HRV insight `[2]`
399. Habit / protocol tracking `[3]`
400. Personalized prevention plan (informational) ✦`[3]`
401. Family-history-based risk `[2]`
402. Environmental / exposome `[3]`
403. Women's-health lifecycle `[2]`
404. Men's-health lifecycle `[2]`
405. Pediatric growth / milestones `[2]`
406. Mental-health check-ins + resources `[2]`
407. Reproductive / fertility planning `[3]`
408. Menopause / andropause support `[3]`
409. Functional-medicine protocol view (labeled) `[3]`

## 20 · Research, commons & data-dividend
410. Opt-in de-identified research contribution ✦`[2]`
411. Study matching (find trials for you) `[3]`
412. Consent-scoped dataset donation ✦`[3]`
413. Data-dividend payout (consent economy) ✦`[3]`
414. Real-world-evidence marketplace (governed) ✦`[3]`
415. Citizen-science cohorts `[3]`
416. Aggregate insights returned to you ✦`[3]`
417. IRB / governance workflow `[3]`
418. Provenance on contributed data ✦`[2]`
419. Revoke research participation anytime ✦`[2]`
420. Federated analysis (data never leaves node) ✦`[3]`
421. Bridge-claim evidence crowdsourcing (tiered) `[3]`
422. Open health-commons contribution (CC) `[3]`
423. Benchmark your metrics vs consented cohort ✦`[3]`
424. Differential-privacy aggregates ✦`[3]`

## 21 · Platform, agents & extensibility
425. Agent SDK over the record (governed) ✦`[2]`
426. Third-party app marketplace (scoped grants) ✦`[3]`
427. FHIR API for authorized apps `[2]`
428. Webhooks / subscriptions (FHIR Subscription) `[3]`
429. Plugin architecture (connectors, views) `[3]`
430. Local model runtime (on-device AI) ✦`[2]`
431. MCP / tool integration (governed) ✦`[3]`
432. Automations ("if lab X, remind me") `[3]`
433. Export to research / analysis tools `[2]`
434. Developer console + docs `[3]`
435. Rate-limit + abuse controls `[2]`
436. Sandbox with synthetic data ✦`[1]`
437. Versioned API + deprecation policy `[2]`
438. Multi-tenant B2B deployment `[3]`
439. White-label for providers/payers `[3]`
440. Interop conformance tests (Inferno/Touchstone) `[2]`

## 22 · Body-state x(t) predictive model
*Edge ✦: a real dynamical model of you — trajectories with uncertainty, heavily guardrailed.*
441. Compartment state model (cardio/renal/hepatic/neuro/…) `[3]`
442. State estimation (Kalman/EKF/particle) `[3]`
443. Mechanistic + learned hybrid (reconciled) `[3]`
444. Trajectory projection (informational, guarded) ✦`[3]`
445. Uncertainty / confidence bands ✦`[3]`
446. Wearable + lab fusion into state ✦`[3]`
447. "What-if" scenario (lifestyle change) ✦`[3]`
448. Human-protection-envelope (HPL) gating ✦`[3]`
449. Omega-state / epistemic promotion of estimates ✦`[3]`
450. Non-actionable-until-consented gate ✦`[2]`
451. Model provenance + replay ✦`[3]`
452. Digital-twin simulation (organ-level, research) `[3]`

---

## How we bury them (the integration thesis)
No competitor holds more than a slice of this atlas. Apple has §1–2 (aggregation) but none of §8–10,
§12's cryptographic consent, or §14's sovereignty. Twin Health has a narrow §22. BioDigital has a
generic §8. Health Gorilla has §1 plumbing. **We build the superset — sovereign, AI-first,
ontology-reasoned, consent-governed — and the §10 bridge nobody else will touch.** The wedge is §1 +
§12 (real ingestion + governed consent); the moat is §8–10 + §22 (the reasoned, bridged, predictive
twin); the market structure is §12 + §20 (the consent economy). Everything is tagged so the roadmap
falls out of the tiers: ship `[0]` → `[1]` → `[2]`, keep `[3]` on the horizon.

*Counts: ~452 numbered features across 22 domains (the "top 500" superset; expand within any domain as
research deepens — the second market-survey pass folds specifics into §1–7 and §16–19).*
