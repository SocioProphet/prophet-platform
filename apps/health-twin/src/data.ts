// The Digital Health Twin engine's data model — FHIR-lite (a walking-skeleton subset of FHIR R4)
// keyed to organ SYSTEMS so the anatomical body diagram can be the index. In production this store is
// LOCAL-FIRST and SOVEREIGN (it runs on the person's own node / BearBrowser sidecar, encrypted, never
// a shared cloud). Here it holds ONE clearly-SYNTHETIC subject so the surface renders — no real PHI.
//
// Trust rides the epistemic ramp: self-reported → lab-verified → clinician-attested. Nothing here is
// diagnostic: the twin organises and retrieves records; a clinician diagnoses.

export type EpistemicMode = 'observed' | 'derived' | 'verified' | 'attested' | 'hypothesis';

// Ontology IRIs — the twin's facts carry real class identity from the HDT ontology, so they land in
// HellGraph as typed nodes (not label strings) and reason in the estate's canonical vocabulary.
//   • HEALTH_NS = the health/anatomy layer (ontogenesis Domains/health-anatomy.ttl, hosted socioprophet.md)
//   • HDT_NS    = the Ontogenesis HDT core (hdt:Observation ⊑ hdt:FHIRResource)
export const HEALTH_NS = 'https://socioprophet.md/ont/health#';
export const HDT_NS = 'https://socioprophet.dev/ont/ontogenesis#';
export const OBSERVATION_CLASS = `${HDT_NS}Observation`;
export const CONDITION_CLASS = `${HEALTH_NS}Condition`;

// Organ systems = the anatomical index. `iri` = the health:OrganSystem class; `compartment` = the
// body-state x(t) compartment; keys match the ontology's health:systemKey.
export interface System { id: string; label: string; organs: string[]; iri: string; compartment: string }
export const SYSTEMS: System[] = [
  { id: 'nervous', label: 'Nervous', organs: ['Brain'], iri: `${HEALTH_NS}NervousSystem`, compartment: 'neuro' },
  { id: 'cardiovascular', label: 'Cardiovascular', organs: ['Heart'], iri: `${HEALTH_NS}CardiovascularSystem`, compartment: 'cardio' },
  { id: 'respiratory', label: 'Respiratory', organs: ['Lungs'], iri: `${HEALTH_NS}RespiratorySystem`, compartment: 'respiratory' },
  { id: 'hepatic', label: 'Hepatic / Digestive', organs: ['Liver', 'Stomach', 'Pancreas', 'Intestines'], iri: `${HEALTH_NS}DigestiveSystem`, compartment: 'hepatic' },
  { id: 'urinary', label: 'Urinary', organs: ['Kidneys', 'Bladder'], iri: `${HEALTH_NS}UrinarySystem`, compartment: 'renal' },
  { id: 'musculoskeletal', label: 'Musculoskeletal', organs: ['Knee'], iri: `${HEALTH_NS}MusculoskeletalSystem`, compartment: 'musculoskeletal' },
];

// Organ → health:Organ IRI (the localizedTo target that paints a record onto anatomy).
export const ORGAN_IRI: Record<string, string> = {
  Brain: `${HEALTH_NS}Brain`, Heart: `${HEALTH_NS}Heart`, Lungs: `${HEALTH_NS}Lungs`,
  Liver: `${HEALTH_NS}Liver`, Stomach: `${HEALTH_NS}Stomach`, Pancreas: `${HEALTH_NS}Pancreas`,
  Intestines: `${HEALTH_NS}Intestines`, Kidneys: `${HEALTH_NS}Kidneys`, Bladder: `${HEALTH_NS}Bladder`,
  Knee: `${HEALTH_NS}Knee`,
};

// `organ` = the anatomical structure this record localises to (health:localizedTo) — what paints it onto the twin.
export interface Observation {
  id: string; system: string; organ: string; code: string; codeSystem: 'LOINC'; display: string;
  value: number; unit: string; refLow?: number; refHigh?: number;
  effective: string; trend?: number[]; epistemic: EpistemicMode;
}
export interface Condition {
  id: string; system: string; organ: string; code: string; codeSystem: 'SNOMED'; display: string;
  onset: string; clinicalStatus: string; epistemic: EpistemicMode;
}
export interface Encounter { id: string; system: string; type: string; date: string; provider: string; note: string }
export interface ImagingStudy { id: string; system: string; modality: string; bodySite: string; date: string; description: string; epistemic: EpistemicMode }

export interface Grant {
  id: string; agent: string; scope: string; granted_at: string; expires_at: string;
  revoked: boolean; reads: number; receipt: string;
  // structured consent scope (systems/kinds/lookback) — `scope` stays the human-readable label.
  // Type-only import from grants.js: no runtime cycle.
  scopeSpec?: import('./grants.js').GrantScope;
}

// ── clearly-synthetic seed (NOT real PHI) ────────────────────────────────────────────────────────
// ageBand/sex are COARSENED demographics: clinically essential (a doctor needs them) and not direct
// identifiers (HIPAA Safe Harbor permits age <90). They survive de-identification under the default
// disclosure scope; exact DOB, name, and contacts never do.
export const SUBJECT = { id: 'synthetic-subject-0', label: 'Demo Patient (synthetic)', note: 'Synthetic sample data — not a real person, not real medical records.', ageBand: '50s', sex: 'male' };

export const OBSERVATIONS: Observation[] = [
  { id: 'obs-ldl', system: 'cardiovascular', organ: 'Heart', code: '13457-7', codeSystem: 'LOINC', display: 'LDL cholesterol', value: 148, unit: 'mg/dL', refLow: 0, refHigh: 100, effective: '2026-05-02', epistemic: 'verified', trend: [121, 126, 130, 129, 138, 142, 148] },
  { id: 'obs-sbp', system: 'cardiovascular', organ: 'Heart', code: '8480-6', codeSystem: 'LOINC', display: 'Systolic blood pressure', value: 138, unit: 'mmHg', refLow: 90, refHigh: 120, effective: '2026-05-02', epistemic: 'verified', trend: [128, 132, 130, 135, 134, 139, 138] },
  { id: 'obs-a1c', system: 'hepatic', organ: 'Pancreas', code: '4548-4', codeSystem: 'LOINC', display: 'Hemoglobin A1c', value: 5.9, unit: '%', refLow: 4, refHigh: 5.6, effective: '2026-04-18', epistemic: 'verified', trend: [5.4, 5.5, 5.6, 5.7, 5.8, 5.8, 5.9] },
  { id: 'obs-alt', system: 'hepatic', organ: 'Liver', code: '1742-6', codeSystem: 'LOINC', display: 'ALT (liver enzyme)', value: 31, unit: 'U/L', refLow: 7, refHigh: 56, effective: '2026-04-18', epistemic: 'verified', trend: [24, 26, 25, 28, 29, 30, 31] },
  { id: 'obs-egfr', system: 'urinary', organ: 'Kidneys', code: '33914-3', codeSystem: 'LOINC', display: 'eGFR (kidney function)', value: 92, unit: 'mL/min', refLow: 90, refHigh: 120, effective: '2026-04-18', epistemic: 'verified', trend: [99, 98, 97, 95, 94, 93, 92] },
];

export const CONDITIONS: Condition[] = [
  { id: 'cond-htn', system: 'cardiovascular', organ: 'Heart', code: '38341003', codeSystem: 'SNOMED', display: 'Essential hypertension', onset: '2024-11-10', clinicalStatus: 'active', epistemic: 'attested' },
  { id: 'cond-pre', system: 'hepatic', organ: 'Pancreas', code: '714628002', codeSystem: 'SNOMED', display: 'Prediabetes', onset: '2026-04-18', clinicalStatus: 'active', epistemic: 'verified' },
];

export const ENCOUNTERS: Encounter[] = [
  { id: 'enc-mri', system: 'nervous', type: 'Imaging — Brain MRI', date: '2026-05-20', provider: 'Radiology', note: 'Routine surveillance; no acute findings noted in report.' },
  { id: 'enc-card', system: 'cardiovascular', type: 'Cardiology consult', date: '2026-05-02', provider: 'Dr. A. Rivera', note: 'BP + lipids reviewed; lifestyle plan; recheck in 3 months.' },
  { id: 'enc-lab', system: 'hepatic', type: 'Lab draw — metabolic panel', date: '2026-04-18', provider: 'LabCorp', note: 'A1c, ALT, eGFR, lipid panel.' },
  { id: 'enc-pcp', system: 'cardiovascular', type: 'Primary care visit', date: '2024-11-10', provider: 'Dr. J. Okafor', note: 'Hypertension diagnosed; started monitoring.' },
  { id: 'enc-knee', system: 'musculoskeletal', type: 'ER visit — knee injury', date: '2003-06-14', provider: 'Pediatric ER', note: 'Fell off a bike aged 9. Left knee X-ray showed no fracture — diagnosed a sprain; RICE + rest. Follow-up at 3 weeks: full recovery, no lasting damage.' },
];

export const IMAGING: ImagingStudy[] = [
  { id: 'img-mri', system: 'nervous', modality: 'MRI', bodySite: 'Brain', date: '2026-05-20', description: 'MRI brain w/o contrast', epistemic: 'attested' },
  { id: 'img-cxr', system: 'respiratory', modality: 'X-ray', bodySite: 'Chest', date: '2025-09-14', description: 'Chest radiograph, PA + lateral', epistemic: 'attested' },
  { id: 'img-knee', system: 'musculoskeletal', modality: 'X-ray', bodySite: 'Knee', date: '2003-06-14', description: 'Left knee radiograph — no fracture; soft-tissue swelling consistent with sprain', epistemic: 'attested' },
];

// Medications, allergies, immunizations — the parts a real twin needs that the seed was missing. The
// person is on lisinopril (for hypertension) but NOT on a statin despite LDL 148 + HTN — a care gap the
// guideline reasoner now catches.
export interface Medication { id: string; system: string; organ: string; code: string; codeSystem: 'RxNorm'; display: string; dose: string; status: string; started: string; epistemic: EpistemicMode }
export const MEDICATIONS: Medication[] = [
  { id: 'med-lisinopril', system: 'cardiovascular', organ: 'Heart', code: '314076', codeSystem: 'RxNorm', display: 'Lisinopril 10 MG Oral Tablet', dose: '10 mg once daily', status: 'active', started: '2024-11-10', epistemic: 'attested' },
];
export interface Allergy { id: string; code: string; codeSystem: 'RxNorm'; display: string; reaction: string; criticality: string; epistemic: EpistemicMode }
export const ALLERGIES: Allergy[] = [
  { id: 'alg-pcn', code: '7980', codeSystem: 'RxNorm', display: 'Penicillin', reaction: 'hives', criticality: 'high', epistemic: 'attested' },
];
export interface Immunization { id: string; code: string; codeSystem: 'CVX'; display: string; date: string; epistemic: EpistemicMode }
export const IMMUNIZATIONS: Immunization[] = [
  { id: 'imm-flu', code: '158', codeSystem: 'CVX', display: 'Influenza (quadrivalent)', date: '2025-10-04', epistemic: 'attested' },
  { id: 'imm-tdap', code: '115', codeSystem: 'CVX', display: 'Tdap', date: '2019-03-11', epistemic: 'attested' },
];
