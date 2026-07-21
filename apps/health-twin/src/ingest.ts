// The ingestion plane — the #1 wedge and the answer to the HealthVault/Watson post-mortem
// (docs/design/digital-health-twin-postmortem-and-ingestion.md). Every source is a Connector split into
// two halves: fetch(mode) is the TRANSPORT (fixture → sandbox → live — the only part that differs by
// mode), normalize(raw) is the ADAPTER (identical in every mode). Because normalize is identical, a
// connector that correctly normalizes a real-schema FIXTURE has a proven LIVE path — so we prove the
// whole pipeline with zero paid feeds and zero real PHI, and flip to live with `mode='live'` + a
// credential. Nothing here diagnoses; every ingested fact lands with PROVENANCE + an epistemic tier
// (the lineage Watson Health never had).
import { HEALTH_NS, HDT_NS, ORGAN_IRI, type Observation, type Condition, type ImagingStudy, type EpistemicMode } from './data.js';

export type SourceId =
  | 'apple-health' | 'google-health-connect' | 'oura' | 'fitbit' | 'dexcom' | 'withings'
  | 'epic-smart-fhir' | 'cms-blue-button' | 'dicomweb' | 'ccda' | 'manual';
export type ConnectorKind = 'wearable' | 'ehr' | 'claims' | 'imaging' | 'lab' | 'document';
export type AuthModel =
  | 'oauth2-smart-on-fhir' | 'oauth2' | 'healthkit-on-device' | 'client-credentials'
  | 'dicomweb-qido' | 'file-upload' | 'manual';
export type IngestMode = 'fixture' | 'sandbox' | 'live';

// Provenance rides on every fact: what came from where, how, when, in what shape, as which USCDI class.
export interface Provenance {
  source: SourceId;
  connector: string;
  authModel: AuthModel;
  mode: IngestMode;
  retrievedAt: string;
  sourceShape: string; // e.g. 'HealthKit HKQuantitySample', 'FHIR R4 Observation (US Core)'
  uscdi: string;       // USCDI v6 data class, e.g. 'Vital Signs', 'Laboratory', 'Medications'
}

// Canonical record shapes not already in data.ts (medications / immunizations / allergies / coverage).
export interface MedicationRecord {
  id: string; system: string; organ: string; code: string; codeSystem: 'RxNorm' | 'NDC';
  display: string; status: string; effective: string; epistemic: EpistemicMode;
}
export interface ImmunizationRecord {
  id: string; code: string; codeSystem: 'CVX'; display: string; occurrence: string; epistemic: EpistemicMode;
}
export interface AllergyRecord {
  id: string; code: string; codeSystem: 'RxNorm' | 'SNOMED'; display: string; criticality: string; epistemic: EpistemicMode;
}
export interface CoverageRecord {
  id: string; payer: string; kind: string; status: string; period: string; epistemic: EpistemicMode;
}

// Each normalized record carries its provenance. The twin never holds a fact without lineage.
export type Provenanced<T> = T & { provenance: Provenance };

export interface IngestResult {
  observations: Provenanced<Observation>[];
  conditions: Provenanced<Condition>[];
  medications: Provenanced<MedicationRecord>[];
  immunizations: Provenanced<ImmunizationRecord>[];
  allergies: Provenanced<AllergyRecord>[];
  imaging: Provenanced<ImagingStudy>[];
  coverage: Provenanced<CoverageRecord>[];
}
export const emptyResult = (): IngestResult => ({
  observations: [], conditions: [], medications: [], immunizations: [], allergies: [], imaging: [], coverage: [],
});

export interface Connector {
  id: SourceId;
  name: string;
  kind: ConnectorKind;
  authModel: AuthModel;
  sourceShape: string;
  uscdiClasses: string[];
  modes: IngestMode[]; // which transports are wired (fixture always; sandbox/live where a rail exists)
  // TRANSPORT — the only mode-dependent half. fixture reads a real-schema payload; live/sandbox is where
  // a real authed HTTP call goes (same return shape, so normalize is untouched).
  fetch(mode: IngestMode): Promise<unknown>;
  // ADAPTER — identical across modes. Maps the real provider shape → canonical, USCDI-typed, provenanced.
  normalize(raw: unknown, mode: IngestMode): IngestResult;
}

// ── shared normalization helpers ─────────────────────────────────────────────────────────────────
// LOINC/organ routing so an ingested vital/lab localizes onto the anatomical twin (health:localizedTo).
const LOINC_ROUTE: Record<string, { system: string; organ: string }> = {
  '8867-4': { system: 'cardiovascular', organ: 'Heart' },   // heart rate
  '40443-4': { system: 'cardiovascular', organ: 'Heart' },  // resting heart rate
  '80404-7': { system: 'cardiovascular', organ: 'Heart' },  // HRV (R-R SDNN)
  '8480-6': { system: 'cardiovascular', organ: 'Heart' },   // systolic BP
  '8462-4': { system: 'cardiovascular', organ: 'Heart' },   // diastolic BP
  '59408-5': { system: 'respiratory', organ: 'Lungs' },     // SpO2
  '9279-1': { system: 'respiratory', organ: 'Lungs' },      // respiratory rate
  '55423-8': { system: 'cardiovascular', organ: 'Heart' },  // steps
  '29463-7': { system: 'hepatic', organ: 'Pancreas' },      // body weight (metabolic proxy)
  '13457-7': { system: 'cardiovascular', organ: 'Heart' },  // LDL
  '4548-4': { system: 'hepatic', organ: 'Pancreas' },       // A1c
  '1742-6': { system: 'hepatic', organ: 'Liver' },          // ALT
  '33914-3': { system: 'urinary', organ: 'Kidneys' },       // eGFR
};
export const routeLoinc = (code: string): { system: string; organ: string } =>
  LOINC_ROUTE[code] ?? { system: 'cardiovascular', organ: 'Heart' };

export const provenance = (
  c: Connector, mode: IngestMode, sourceShape: string, uscdi: string,
): Provenance => ({
  source: c.id, connector: c.name, authModel: c.authModel, mode,
  retrievedAt: new Date().toISOString(), sourceShape, uscdi,
});

// enrich an observation/condition/imaging with its ontology IRIs (typed node, not a label string).
export const withObsIri = (o: Observation) => ({ ...o, classIri: `${HDT_NS}Observation`, organIri: ORGAN_IRI[o.organ] ?? null });
export const withCondIri = (c: Condition) => ({ ...c, classIri: `${HEALTH_NS}Condition`, organIri: ORGAN_IRI[c.organ] ?? null });

// merge many IngestResults, deduping by record id (cross-source reconciliation, richest-tier wins).
const TIER_RANK: Record<EpistemicMode, number> = { hypothesis: 0, observed: 1, derived: 2, verified: 3, attested: 4 };
export function mergeResults(results: IngestResult[]): IngestResult {
  const out = emptyResult();
  const seen = new Map<string, { tier: number; bucket: any[]; idx: number }>();
  const add = (bucket: any[], rec: any) => {
    const key = `${bucket === out.observations ? 'obs' : bucket === out.conditions ? 'cond' : 'x'}:${rec.id}`;
    const tier = TIER_RANK[(rec.epistemic as EpistemicMode) ?? 'observed'] ?? 1;
    const prior = seen.get(key);
    if (prior) { if (tier > prior.tier) { prior.bucket[prior.idx] = rec; prior.tier = tier; } return; }
    seen.set(key, { tier, bucket, idx: bucket.length }); bucket.push(rec);
  };
  for (const r of results) {
    r.observations.forEach((x) => add(out.observations, x));
    r.conditions.forEach((x) => add(out.conditions, x));
    out.medications.push(...r.medications);
    out.immunizations.push(...r.immunizations);
    out.allergies.push(...r.allergies);
    out.imaging.push(...r.imaging);
    out.coverage.push(...r.coverage);
  }
  return out;
}

export const resultCounts = (r: IngestResult) => ({
  observations: r.observations.length, conditions: r.conditions.length, medications: r.medications.length,
  immunizations: r.immunizations.length, allergies: r.allergies.length, imaging: r.imaging.length,
  coverage: r.coverage.length,
  total: r.observations.length + r.conditions.length + r.medications.length + r.immunizations.length +
    r.allergies.length + r.imaging.length + r.coverage.length,
});
