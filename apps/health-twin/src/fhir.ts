// fhir.ts — the interoperability plane (verbs 1 Observe + 2 Structure). The twin already speaks a
// FHIR-lite internal model; this renders it as a real HL7 **FHIR R4** Bundle (Patient + Observation +
// Condition + MedicationStatement + AllergyIntolerance + Immunization) and parses a FHIR Bundle back
// into twin records. That's how we read and write the real healthcare system — the NEPHRO-DIGITAL
// interop layer (openEHR/IHE-XDS/FHIR) — and then layer reasoning (triage/monitor/evidence) on top,
// which their stack does not have. Codes carry their real systems (LOINC/SNOMED/RxNorm/CVX). The
// export is de-identified by default at the Patient level (age band + sex, never name/DOB).
import { SUBJECT, OBSERVATIONS, CONDITIONS, MEDICATIONS, ALLERGIES, IMMUNIZATIONS } from './data.js';

const CODE_SYSTEM: Record<string, string> = {
  LOINC: 'http://loinc.org',
  SNOMED: 'http://snomed.info/sct',
  RxNorm: 'http://www.nlm.nih.gov/research/umls/rxnorm',
  CVX: 'http://hl7.org/fhir/sid/cvx',
};
const SEX_TO_GENDER: Record<string, string> = { male: 'male', female: 'female' };

interface FhirEntry { resource: Record<string, any> }
export interface FhirBundle { resourceType: 'Bundle'; type: 'collection'; timestamp: string; entry: FhirEntry[] }

const coding = (system: string, code: string, display: string) => ({ coding: [{ system: CODE_SYSTEM[system] ?? system, code, display }], text: display });
const patientRef = () => ({ reference: `Patient/${SUBJECT.id}` });

// Twin → FHIR R4 Bundle. Patient stays de-identified (coarsened age band + sex; no name/DOB) — the
// same disclosure floor the rest of the twin enforces.
export function toFhirBundle(): FhirBundle {
  const s = SUBJECT as any;
  const entry: FhirEntry[] = [];

  entry.push({ resource: {
    resourceType: 'Patient', id: SUBJECT.id,
    gender: SEX_TO_GENDER[s.sex] ?? 'unknown',
    // age band as an extension (Safe-Harbor-safe); NEVER birthDate/name here
    extension: s.ageBand ? [{ url: 'https://socioprophet.md/fhir/age-band', valueString: s.ageBand }] : [],
  } });

  for (const o of OBSERVATIONS) entry.push({ resource: {
    resourceType: 'Observation', id: o.id, status: 'final',
    code: coding(o.codeSystem, o.code, o.display),
    subject: patientRef(), effectiveDateTime: o.effective,
    valueQuantity: { value: o.value, unit: o.unit, system: 'http://unitsofmeasure.org' },
    referenceRange: (o.refLow != null || o.refHigh != null) ? [{
      ...(o.refLow != null ? { low: { value: o.refLow, unit: o.unit } } : {}),
      ...(o.refHigh != null ? { high: { value: o.refHigh, unit: o.unit } } : {}),
    }] : undefined,
  } });

  for (const c of CONDITIONS) entry.push({ resource: {
    resourceType: 'Condition', id: c.id,
    clinicalStatus: { coding: [{ system: 'http://terminology.hl7.org/CodeSystem/condition-clinical', code: c.clinicalStatus }] },
    code: coding(c.codeSystem, c.code, c.display),
    subject: patientRef(), onsetDateTime: c.onset,
  } });

  for (const m of MEDICATIONS) entry.push({ resource: {
    resourceType: 'MedicationStatement', id: m.id, status: m.status,
    medicationCodeableConcept: coding(m.codeSystem, m.code, m.display),
    subject: patientRef(), effectiveDateTime: m.started,
    dosage: [{ text: m.dose }],
  } });

  for (const a of ALLERGIES) entry.push({ resource: {
    resourceType: 'AllergyIntolerance', id: a.id,
    criticality: a.criticality,
    code: coding(a.codeSystem, a.code, a.display),
    patient: patientRef(),
    reaction: [{ manifestation: [{ text: a.reaction }] }],
  } });

  for (const im of IMMUNIZATIONS) entry.push({ resource: {
    resourceType: 'Immunization', id: im.id, status: 'completed',
    vaccineCode: coding(im.codeSystem, im.code, im.display),
    patient: patientRef(), occurrenceDateTime: im.date,
  } });

  return { resourceType: 'Bundle', type: 'collection', timestamp: new Date().toISOString(), entry };
}

export interface ParsedFhir {
  observations: { code: string; codeSystem: string; display: string; value?: number; unit?: string; effective?: string; refLow?: number; refHigh?: number }[];
  conditions: { code: string; codeSystem: string; display: string; clinicalStatus?: string; onset?: string }[];
  counts: { observations: number; conditions: number; skipped: number };
}

const SYSTEM_NAME: Record<string, string> = Object.fromEntries(Object.entries(CODE_SYSTEM).map(([k, v]) => [v, k]));

// FHIR Bundle → twin records (Observation + Condition — the two the reasoning layer consumes). Tolerant
// of partial/foreign bundles: anything it can't map is counted as skipped, never silently dropped.
export function fromFhirBundle(bundle: any): ParsedFhir {
  const out: ParsedFhir = { observations: [], conditions: [], counts: { observations: 0, conditions: 0, skipped: 0 } };
  const entries: any[] = Array.isArray(bundle?.entry) ? bundle.entry : [];
  for (const e of entries) {
    const r = e?.resource ?? e;
    const c0 = r?.code?.coding?.[0];
    if (r?.resourceType === 'Observation' && c0) {
      out.observations.push({
        code: String(c0.code), codeSystem: SYSTEM_NAME[c0.system] ?? c0.system ?? 'unknown',
        display: c0.display ?? r.code?.text ?? '', value: r.valueQuantity?.value, unit: r.valueQuantity?.unit,
        effective: r.effectiveDateTime, refLow: r.referenceRange?.[0]?.low?.value, refHigh: r.referenceRange?.[0]?.high?.value,
      });
      out.counts.observations++;
    } else if (r?.resourceType === 'Condition' && c0) {
      out.conditions.push({
        code: String(c0.code), codeSystem: SYSTEM_NAME[c0.system] ?? c0.system ?? 'unknown',
        display: c0.display ?? r.code?.text ?? '', clinicalStatus: r.clinicalStatus?.coding?.[0]?.code, onset: r.onsetDateTime,
      });
      out.counts.conditions++;
    } else {
      out.counts.skipped++;
    }
  }
  return out;
}
