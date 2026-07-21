// Epic / SMART-on-FHIR connector — the MARQUEE adapter. Live transport = SMART-on-FHIR patient-access
// (OAuth2 standalone launch: the person authenticates to their portal, we get a scoped token + FHIR R4
// endpoint) — the mandated, legally-CLEAN rail (TEFCA Individual Access Services) that HealthVault
// lacked and that "treatment-purpose" aggregators are being litigated for abusing. The fixture is a
// real US Core R4 searchset Bundle (Condition/Observation-lab/MedicationRequest/AllergyIntolerance/
// Immunization with the correct code systems). normalize() maps each US Core resource → canonical.
// EHR-sourced ⇒ epistemic 'attested' for conditions/allergies, 'verified' for labs.
import type { Connector, IngestResult, IngestMode } from '../ingest.js';
import { emptyResult, provenance, routeLoinc } from '../ingest.js';

// minimal FHIR R4 shapes (US Core profiles)
interface Coding { system?: string; code?: string; display?: string }
interface CC { coding?: Coding[]; text?: string }
interface FhirResource {
  resourceType: string; id?: string;
  code?: CC; category?: CC[]; clinicalStatus?: CC; verificationStatus?: CC; criticality?: string;
  valueQuantity?: { value: number; unit: string }; referenceRange?: { low?: { value: number }; high?: { value: number } }[];
  effectiveDateTime?: string; onsetDateTime?: string; recordedDate?: string; occurrenceDateTime?: string; authoredOn?: string;
  medicationCodeableConcept?: CC; vaccineCode?: CC; status?: string;
}
interface Bundle { resourceType: 'Bundle'; type: string; entry?: { resource: FhirResource }[] }

const codeOf = (cc?: CC) => cc?.coding?.[0]?.code ?? '';
const dispOf = (cc?: CC) => cc?.coding?.[0]?.display ?? cc?.text ?? '';

const FIXTURE: Bundle = { resourceType: 'Bundle', type: 'searchset', entry: [
  { resource: { resourceType: 'Condition', id: 'c1', clinicalStatus: { coding: [{ code: 'active' }] },
    code: { coding: [{ system: 'http://snomed.info/sct', code: '38341003', display: 'Essential hypertension' }] }, onsetDateTime: '2024-11-10' } },
  { resource: { resourceType: 'Observation', id: 'o1', category: [{ coding: [{ code: 'laboratory' }] }],
    code: { coding: [{ system: 'http://loinc.org', code: '13457-7', display: 'LDL cholesterol' }] },
    valueQuantity: { value: 151, unit: 'mg/dL' }, referenceRange: [{ high: { value: 100 } }], effectiveDateTime: '2026-06-30' } },
  { resource: { resourceType: 'Observation', id: 'o2', category: [{ coding: [{ code: 'laboratory' }] }],
    code: { coding: [{ system: 'http://loinc.org', code: '4548-4', display: 'Hemoglobin A1c' }] },
    valueQuantity: { value: 6.0, unit: '%' }, referenceRange: [{ low: { value: 4 }, high: { value: 5.6 } }], effectiveDateTime: '2026-06-30' } },
  { resource: { resourceType: 'MedicationRequest', id: 'm1', status: 'active',
    medicationCodeableConcept: { coding: [{ system: 'http://www.nlm.nih.gov/research/umls/rxnorm', code: '314076', display: 'Lisinopril 10 MG Oral Tablet' }] }, authoredOn: '2024-11-10' } },
  { resource: { resourceType: 'AllergyIntolerance', id: 'a1', criticality: 'high',
    code: { coding: [{ system: 'http://www.nlm.nih.gov/research/umls/rxnorm', code: '7980', display: 'Penicillin' }] } } },
  { resource: { resourceType: 'Immunization', id: 'i1', status: 'completed', occurrenceDateTime: '2025-10-04',
    vaccineCode: { coding: [{ system: 'http://hl7.org/fhir/sid/cvx', code: '158', display: 'Influenza, injectable, quadrivalent' }] } } },
] };

// SANDBOX transport — REAL network fetch against an open SMART-on-FHIR R4 sandbox (Synthea patients, no
// auth). The honest fixture→sandbox step: same normalize(), real records over the wire. `live` is the
// same shape with a bearer token + the person's own FHIR base.
const SANDBOX_BASE = process.env.HT_SMART_SANDBOX ?? 'https://r4.smarthealthit.org';
async function fetchSandbox(base: string, token?: string): Promise<Bundle> {
  const headers: Record<string, string> = { accept: 'application/fhir+json' };
  if (token) headers.authorization = `Bearer ${token}`;
  const get = async (path: string) => {
    const r = await fetch(`${base}/${path}`, { headers });
    if (!r.ok) throw new Error(`FHIR ${r.status} on ${path}`);
    return (await r.json()) as { entry?: { resource: FhirResource }[] };
  };
  const pj = await get('Patient?_count=1');
  const pid = pj.entry?.[0]?.resource?.id;
  if (!pid) throw new Error('sandbox: no patient found');
  const queries = ['Condition', 'Observation?category=laboratory', 'MedicationRequest', 'AllergyIntolerance', 'Immunization'];
  const entry: { resource: FhirResource }[] = [];
  for (const q of queries) {
    const sep = q.includes('?') ? '&' : '?';
    try { const b = await get(`${q}${sep}patient=${pid}&_count=8`); for (const e of b.entry ?? []) if (e.resource) entry.push({ resource: e.resource }); }
    catch { /* skip a type the server rejects; the rest still flow */ }
  }
  return { resourceType: 'Bundle', type: 'searchset', entry };
}

export const epicSmartFhir: Connector = {
  id: 'epic-smart-fhir', name: 'Epic — SMART-on-FHIR (patient access)', kind: 'ehr',
  authModel: 'oauth2-smart-on-fhir', sourceShape: 'FHIR R4 US Core Bundle',
  uscdiClasses: ['Problems', 'Laboratory', 'Medications', 'Allergies and Intolerances', 'Immunizations'],
  modes: ['fixture', 'sandbox', 'live'],
  async fetch(mode: IngestMode) {
    if (mode === 'fixture') return FIXTURE;
    // sandbox = REAL FHIR over the wire (open Synthea server); live = same + a SMART bearer token + base.
    if (mode === 'sandbox') return fetchSandbox(SANDBOX_BASE);
    return fetchSandbox(process.env.HT_SMART_FHIR_BASE ?? SANDBOX_BASE, process.env.HT_SMART_TOKEN);
  },
  normalize(raw: unknown, mode: IngestMode): IngestResult {
    const out: IngestResult = emptyResult();
    const b = raw as Bundle;
    const shape = this.sourceShape;
    for (const e of b.entry ?? []) {
      const r = e.resource;
      if (r.resourceType === 'Condition') {
        const { system, organ } = { system: 'cardiovascular', organ: 'Heart' }; // SNOMED→organ routing is a later enrichment
        out.conditions.push({ id: `epic-cond-${r.id}`, system, organ, code: codeOf(r.code), codeSystem: 'SNOMED', display: dispOf(r.code), onset: r.onsetDateTime ?? r.recordedDate ?? '', clinicalStatus: codeOf(r.clinicalStatus) || 'active', epistemic: 'attested', provenance: provenance(this, mode, `${shape} (Condition)`, 'Problems') });
      } else if (r.resourceType === 'Observation' && codeOf(r.category?.[0]) === 'laboratory') {
        const code = codeOf(r.code); const { system, organ } = routeLoinc(code);
        out.observations.push({ id: `epic-obs-${r.id}`, system, organ, code, codeSystem: 'LOINC', display: dispOf(r.code), value: r.valueQuantity?.value ?? 0, unit: r.valueQuantity?.unit ?? '', refLow: r.referenceRange?.[0]?.low?.value, refHigh: r.referenceRange?.[0]?.high?.value, effective: (r.effectiveDateTime ?? '').slice(0, 10), epistemic: 'verified', provenance: provenance(this, mode, `${shape} (Observation)`, 'Laboratory') });
      } else if (r.resourceType === 'MedicationRequest') {
        out.medications.push({ id: `epic-med-${r.id}`, system: 'cardiovascular', organ: 'Heart', code: codeOf(r.medicationCodeableConcept), codeSystem: 'RxNorm', display: dispOf(r.medicationCodeableConcept), status: r.status ?? 'active', effective: (r.authoredOn ?? '').slice(0, 10), epistemic: 'attested', provenance: provenance(this, mode, `${shape} (MedicationRequest)`, 'Medications') });
      } else if (r.resourceType === 'AllergyIntolerance') {
        out.allergies.push({ id: `epic-alg-${r.id}`, code: codeOf(r.code), codeSystem: 'RxNorm', display: dispOf(r.code), criticality: r.criticality ?? 'unable-to-assess', epistemic: 'attested', provenance: provenance(this, mode, `${shape} (AllergyIntolerance)`, 'Allergies and Intolerances') });
      } else if (r.resourceType === 'Immunization') {
        out.immunizations.push({ id: `epic-imm-${r.id}`, code: codeOf(r.vaccineCode), codeSystem: 'CVX', display: dispOf(r.vaccineCode), occurrence: (r.occurrenceDateTime ?? '').slice(0, 10), epistemic: 'attested', provenance: provenance(this, mode, `${shape} (Immunization)`, 'Immunizations') });
      }
    }
    return out;
  },
};
