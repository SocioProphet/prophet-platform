// The Digital Health Twin engine's data model — FHIR-lite (a walking-skeleton subset of FHIR R4)
// keyed to organ SYSTEMS so the anatomical body diagram can be the index. In production this store is
// LOCAL-FIRST and SOVEREIGN (it runs on the person's own node / BearBrowser sidecar, encrypted, never
// a shared cloud). Here it holds ONE clearly-SYNTHETIC subject so the surface renders — no real PHI.
//
// Trust rides the epistemic ramp: self-reported → lab-verified → clinician-attested. Nothing here is
// diagnostic: the twin organises and retrieves records; a clinician diagnoses.

export type EpistemicMode = 'observed' | 'derived' | 'verified' | 'attested' | 'hypothesis';

// Organ systems = the anatomical index. `organs` are the diagram labels the poster shows.
export interface System { id: string; label: string; organs: string[] }
export const SYSTEMS: System[] = [
  { id: 'nervous', label: 'Nervous', organs: ['Brain'] },
  { id: 'cardiovascular', label: 'Cardiovascular', organs: ['Heart'] },
  { id: 'respiratory', label: 'Respiratory', organs: ['Lungs'] },
  { id: 'hepatic', label: 'Hepatic / Digestive', organs: ['Liver', 'Stomach', 'Pancreas', 'Intestines'] },
  { id: 'urinary', label: 'Urinary', organs: ['Kidneys', 'Bladder'] },
];

export interface Observation {
  id: string; system: string; code: string; codeSystem: 'LOINC'; display: string;
  value: number; unit: string; refLow?: number; refHigh?: number;
  effective: string; trend?: number[]; epistemic: EpistemicMode;
}
export interface Condition {
  id: string; system: string; code: string; codeSystem: 'SNOMED'; display: string;
  onset: string; clinicalStatus: string; epistemic: EpistemicMode;
}
export interface Encounter { id: string; system: string; type: string; date: string; provider: string; note: string }
export interface ImagingStudy { id: string; system: string; modality: string; bodySite: string; date: string; description: string; epistemic: EpistemicMode }

export interface Grant {
  id: string; agent: string; scope: string; granted_at: string; expires_at: string;
  revoked: boolean; reads: number; receipt: string;
}

// ── clearly-synthetic seed (NOT real PHI) ────────────────────────────────────────────────────────
export const SUBJECT = { id: 'synthetic-subject-0', label: 'Demo Patient (synthetic)', note: 'Synthetic sample data — not a real person, not real medical records.' };

export const OBSERVATIONS: Observation[] = [
  { id: 'obs-ldl', system: 'cardiovascular', code: '13457-7', codeSystem: 'LOINC', display: 'LDL cholesterol', value: 148, unit: 'mg/dL', refLow: 0, refHigh: 100, effective: '2026-05-02', epistemic: 'verified', trend: [121, 126, 130, 129, 138, 142, 148] },
  { id: 'obs-sbp', system: 'cardiovascular', code: '8480-6', codeSystem: 'LOINC', display: 'Systolic blood pressure', value: 138, unit: 'mmHg', refLow: 90, refHigh: 120, effective: '2026-05-02', epistemic: 'verified', trend: [128, 132, 130, 135, 134, 139, 138] },
  { id: 'obs-a1c', system: 'hepatic', code: '4548-4', codeSystem: 'LOINC', display: 'Hemoglobin A1c', value: 5.9, unit: '%', refLow: 4, refHigh: 5.6, effective: '2026-04-18', epistemic: 'verified', trend: [5.4, 5.5, 5.6, 5.7, 5.8, 5.8, 5.9] },
  { id: 'obs-alt', system: 'hepatic', code: '1742-6', codeSystem: 'LOINC', display: 'ALT (liver enzyme)', value: 31, unit: 'U/L', refLow: 7, refHigh: 56, effective: '2026-04-18', epistemic: 'verified', trend: [24, 26, 25, 28, 29, 30, 31] },
  { id: 'obs-egfr', system: 'urinary', code: '33914-3', codeSystem: 'LOINC', display: 'eGFR (kidney function)', value: 92, unit: 'mL/min', refLow: 90, refHigh: 120, effective: '2026-04-18', epistemic: 'verified', trend: [99, 98, 97, 95, 94, 93, 92] },
];

export const CONDITIONS: Condition[] = [
  { id: 'cond-htn', system: 'cardiovascular', code: '38341003', codeSystem: 'SNOMED', display: 'Essential hypertension', onset: '2024-11-10', clinicalStatus: 'active', epistemic: 'attested' },
  { id: 'cond-pre', system: 'hepatic', code: '714628002', codeSystem: 'SNOMED', display: 'Prediabetes', onset: '2026-04-18', clinicalStatus: 'active', epistemic: 'verified' },
];

export const ENCOUNTERS: Encounter[] = [
  { id: 'enc-mri', system: 'nervous', type: 'Imaging — Brain MRI', date: '2026-05-20', provider: 'Radiology', note: 'Routine surveillance; no acute findings noted in report.' },
  { id: 'enc-card', system: 'cardiovascular', type: 'Cardiology consult', date: '2026-05-02', provider: 'Dr. A. Rivera', note: 'BP + lipids reviewed; lifestyle plan; recheck in 3 months.' },
  { id: 'enc-lab', system: 'hepatic', type: 'Lab draw — metabolic panel', date: '2026-04-18', provider: 'LabCorp', note: 'A1c, ALT, eGFR, lipid panel.' },
  { id: 'enc-pcp', system: 'cardiovascular', type: 'Primary care visit', date: '2024-11-10', provider: 'Dr. J. Okafor', note: 'Hypertension diagnosed; started monitoring.' },
];

export const IMAGING: ImagingStudy[] = [
  { id: 'img-mri', system: 'nervous', modality: 'MRI', bodySite: 'Brain', date: '2026-05-20', description: 'MRI brain w/o contrast', epistemic: 'attested' },
  { id: 'img-cxr', system: 'respiratory', modality: 'X-ray', bodySite: 'Chest', date: '2025-09-14', description: 'Chest radiograph, PA + lateral', epistemic: 'attested' },
];
