// terminology.ts — the terminology value sets (SNOMED / LOINC / RxNorm / ICD-10), bound UPWARD into
// the Ontogenesis + HDT world-model. Each concept is not just a code+label: it carries its HDT
// ontology CLASS IRI (hdt:Observation / health:Condition / …), its health: organ + organ-system IRIs,
// and cross-terminology maps (e.g. SNOMED↔ICD-10). So a coded fact types into HellGraph as a real
// node and reasons in Ontogenesis — the terminology is part of the world-model vocabulary, routed
// through ontogenesis, not a downstream lexicon. Emits SKOS/RDF the owl-reasoner + Ontogenesis load.
// Non-diagnostic reference vocabulary.
import { HEALTH_NS, HDT_NS, OBSERVATION_CLASS, CONDITION_CLASS, ORGAN_IRI, SYSTEMS } from './data.js';

export type CodeSystem = 'SNOMED' | 'LOINC' | 'RxNorm' | 'ICD-10' | 'CVX';
export type ConceptCategory = 'condition' | 'observation' | 'medication' | 'allergy' | 'procedure';

const SYSTEM_URI: Record<CodeSystem, string> = {
  SNOMED: 'http://snomed.info/sct', LOINC: 'http://loinc.org',
  RxNorm: 'http://www.nlm.nih.gov/research/umls/rxnorm', 'ICD-10': 'http://hl7.org/fhir/sid/icd-10-cm',
  CVX: 'http://hl7.org/fhir/sid/cvx',
};
const MEDICATION_CLASS = `${HDT_NS}Medication`;
const systemIriOf = (key?: string) => SYSTEMS.find((s) => s.id === key)?.iri;

export interface Concept {
  code: string; system: CodeSystem; display: string; category: ConceptCategory;
  classIri: string;                 // the HDT/Ontogenesis class this concept types as (the upward bind)
  systemKey?: string;               // health: organ-system id (cardiovascular, hepatic, …)
  organ?: string;                   // health: organ name → organIri
  maps?: { system: CodeSystem; code: string }[]; // cross-terminology (SNOMED↔ICD-10, etc.)
}

// Curated value sets — real codes, cardiometabolic wedge + common conditions/labs/meds. Each binds
// to its HDT class + organ/system so it lands in the twin's ontology, not a flat table.
const C = (code: string, system: CodeSystem, display: string, category: ConceptCategory, classIri: string, systemKey?: string, organ?: string, maps?: Concept['maps']): Concept =>
  ({ code, system, display, category, classIri, systemKey, organ, maps });

export const VALUE_SETS: Concept[] = [
  // conditions (SNOMED, mapped to ICD-10) → health:Condition, organ/system bound
  C('38341003', 'SNOMED', 'Essential hypertension', 'condition', CONDITION_CLASS, 'cardiovascular', 'Heart', [{ system: 'ICD-10', code: 'I10' }]),
  C('714628002', 'SNOMED', 'Prediabetes', 'condition', CONDITION_CLASS, 'hepatic', 'Pancreas', [{ system: 'ICD-10', code: 'R73.03' }]),
  C('44054006', 'SNOMED', 'Type 2 diabetes mellitus', 'condition', CONDITION_CLASS, 'hepatic', 'Pancreas', [{ system: 'ICD-10', code: 'E11.9' }]),
  C('55822004', 'SNOMED', 'Hyperlipidemia', 'condition', CONDITION_CLASS, 'cardiovascular', 'Heart', [{ system: 'ICD-10', code: 'E78.5' }]),
  C('13644009', 'SNOMED', 'Hypercholesterolemia', 'condition', CONDITION_CLASS, 'cardiovascular', 'Heart', [{ system: 'ICD-10', code: 'E78.00' }]),
  C('709044004', 'SNOMED', 'Chronic kidney disease', 'condition', CONDITION_CLASS, 'urinary', 'Kidneys', [{ system: 'ICD-10', code: 'N18.9' }]),
  C('84114007', 'SNOMED', 'Heart failure', 'condition', CONDITION_CLASS, 'cardiovascular', 'Heart', [{ system: 'ICD-10', code: 'I50.9' }]),
  C('49436004', 'SNOMED', 'Atrial fibrillation', 'condition', CONDITION_CLASS, 'cardiovascular', 'Heart', [{ system: 'ICD-10', code: 'I48.91' }]),
  C('195967001', 'SNOMED', 'Asthma', 'condition', CONDITION_CLASS, 'respiratory', 'Lungs', [{ system: 'ICD-10', code: 'J45.909' }]),
  C('13645005', 'SNOMED', 'Chronic obstructive pulmonary disease', 'condition', CONDITION_CLASS, 'respiratory', 'Lungs', [{ system: 'ICD-10', code: 'J44.9' }]),
  C('414916001', 'SNOMED', 'Obesity', 'condition', CONDITION_CLASS, 'hepatic', 'Liver', [{ system: 'ICD-10', code: 'E66.9' }]),
  C('35489007', 'SNOMED', 'Depressive disorder', 'condition', CONDITION_CLASS, 'nervous', 'Brain', [{ system: 'ICD-10', code: 'F32.9' }]),
  C('48694002', 'SNOMED', 'Anxiety', 'condition', CONDITION_CLASS, 'nervous', 'Brain', [{ system: 'ICD-10', code: 'F41.9' }]),

  // observations (LOINC) → hdt:Observation, organ bound
  C('13457-7', 'LOINC', 'LDL cholesterol', 'observation', OBSERVATION_CLASS, 'cardiovascular', 'Heart'),
  C('2085-9', 'LOINC', 'HDL cholesterol', 'observation', OBSERVATION_CLASS, 'cardiovascular', 'Heart'),
  C('2093-3', 'LOINC', 'Total cholesterol', 'observation', OBSERVATION_CLASS, 'cardiovascular', 'Heart'),
  C('2571-8', 'LOINC', 'Triglycerides', 'observation', OBSERVATION_CLASS, 'cardiovascular', 'Heart'),
  C('8480-6', 'LOINC', 'Systolic blood pressure', 'observation', OBSERVATION_CLASS, 'cardiovascular', 'Heart'),
  C('8462-4', 'LOINC', 'Diastolic blood pressure', 'observation', OBSERVATION_CLASS, 'cardiovascular', 'Heart'),
  C('4548-4', 'LOINC', 'Hemoglobin A1c', 'observation', OBSERVATION_CLASS, 'hepatic', 'Pancreas'),
  C('1558-6', 'LOINC', 'Fasting glucose', 'observation', OBSERVATION_CLASS, 'hepatic', 'Pancreas'),
  C('33914-3', 'LOINC', 'eGFR', 'observation', OBSERVATION_CLASS, 'urinary', 'Kidneys'),
  C('2160-0', 'LOINC', 'Creatinine', 'observation', OBSERVATION_CLASS, 'urinary', 'Kidneys'),
  C('1742-6', 'LOINC', 'Alanine aminotransferase (ALT)', 'observation', OBSERVATION_CLASS, 'hepatic', 'Liver'),
  C('1920-8', 'LOINC', 'Aspartate aminotransferase (AST)', 'observation', OBSERVATION_CLASS, 'hepatic', 'Liver'),
  C('3016-3', 'LOINC', 'TSH', 'observation', OBSERVATION_CLASS, 'hepatic', 'Pancreas'),
  C('2823-3', 'LOINC', 'Potassium', 'observation', OBSERVATION_CLASS, 'urinary', 'Kidneys'),

  // medications (RxNorm ingredient) → hdt:Medication, organ/system of primary action
  C('29046', 'RxNorm', 'Lisinopril', 'medication', MEDICATION_CLASS, 'cardiovascular', 'Heart'),
  C('52175', 'RxNorm', 'Losartan', 'medication', MEDICATION_CLASS, 'cardiovascular', 'Heart'),
  C('17767', 'RxNorm', 'Amlodipine', 'medication', MEDICATION_CLASS, 'cardiovascular', 'Heart'),
  C('5487', 'RxNorm', 'Hydrochlorothiazide', 'medication', MEDICATION_CLASS, 'urinary', 'Kidneys'),
  C('6918', 'RxNorm', 'Metoprolol', 'medication', MEDICATION_CLASS, 'cardiovascular', 'Heart'),
  C('83367', 'RxNorm', 'Atorvastatin', 'medication', MEDICATION_CLASS, 'cardiovascular', 'Heart'),
  C('36567', 'RxNorm', 'Simvastatin', 'medication', MEDICATION_CLASS, 'cardiovascular', 'Heart'),
  C('6809', 'RxNorm', 'Metformin', 'medication', MEDICATION_CLASS, 'hepatic', 'Pancreas'),
  C('1191', 'RxNorm', 'Aspirin', 'medication', MEDICATION_CLASS, 'cardiovascular', 'Heart'),
];

const norm = (s: string) => s.trim().toLowerCase();
const byKey = new Map<string, Concept>();
for (const c of VALUE_SETS) byKey.set(`${c.system}|${c.code}`, c);

export function valueSet(category?: ConceptCategory) {
  const concepts = category ? VALUE_SETS.filter((c) => c.category === category) : VALUE_SETS;
  return { count: concepts.length, systems: [...new Set(concepts.map((c) => c.system))], concepts };
}

// Resolve a code (system+code) OR free text → the ontogenesis-bound concept.
export function lookup(opts: { system?: CodeSystem; code?: string; q?: string }): Concept | null {
  if (opts.system && opts.code) return byKey.get(`${opts.system}|${opts.code}`) ?? null;
  if (opts.code) return VALUE_SETS.find((c) => c.code === opts.code) ?? null;
  if (opts.q) { const q = norm(opts.q); return VALUE_SETS.find((c) => norm(c.display) === q) ?? VALUE_SETS.find((c) => norm(c.display).includes(q)) ?? null; }
  return null;
}

// Cross-terminology crosswalk (e.g. SNOMED condition → its ICD-10 map, and back).
export function crosswalk(system: CodeSystem, code: string): { from: Concept | null; maps: { system: CodeSystem; code: string; display: string }[] } {
  const c = byKey.get(`${system}|${code}`) ?? VALUE_SETS.find((x) => x.code === code) ?? null;
  const maps = (c?.maps ?? []).map((m) => ({ system: m.system, code: m.code, display: c!.display }));
  return { from: c, maps };
}

// ── the UPWARD bind: emit the value set as SKOS/RDF Ontogenesis + the owl-reasoner consume ──────────
// Each concept becomes a skos:Concept typed as its HDT class (hdt:Observation / health:Condition / …),
// linked to its health: organ + organ-system, with skos:exactMatch to its cross-terminology maps. This
// is what routes the terminology THROUGH ontogenesis (it becomes typed world-model vocabulary).
function conceptIri(c: Concept): string { return `${HEALTH_NS}concept/${c.system}/${encodeURIComponent(c.code)}`; }
function ttlEsc(s: string): string { return s.replace(/\\/g, '\\\\').replace(/"/g, '\\"'); }

export function valueSetTtl(): string {
  const head = [
    `@prefix health: <${HEALTH_NS}> .`,
    `@prefix hdt: <${HDT_NS}> .`,
    '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .',
    '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
    '',
  ];
  const lines: string[] = [];
  for (const c of VALUE_SETS) {
    const iri = `<${conceptIri(c)}>`;
    const parts = [
      `${iri} a skos:Concept, <${c.classIri}> ;`,
      `  skos:notation "${ttlEsc(c.code)}" ;`,
      `  skos:prefLabel "${ttlEsc(c.display)}" ;`,
      `  health:codeSystem "${c.system}" ;`,
      `  health:codeSystemUri <${SYSTEM_URI[c.system]}>`,
    ];
    if (c.organ && ORGAN_IRI[c.organ]) parts.push(` ; health:localizedTo <${ORGAN_IRI[c.organ]}>`);
    const sysIri = systemIriOf(c.systemKey);
    if (sysIri) parts.push(` ; health:inSystem <${sysIri}>`);
    for (const m of c.maps ?? []) parts.push(` ; skos:exactMatch <${HEALTH_NS}concept/${m.system}/${encodeURIComponent(m.code)}>`);
    lines.push(parts.join('') + ' .');
  }
  return head.concat(lines).join('\n') + '\n';
}

// A concept as a typed node ready for HellGraph ingestion (the same shape the twin's facts carry).
export function toOntogenesisNode(c: Concept) {
  return {
    iri: conceptIri(c), classIri: c.classIri, kind: 'skos:Concept',
    code: c.code, codeSystem: c.system, codeSystemUri: SYSTEM_URI[c.system], display: c.display,
    organIri: c.organ ? ORGAN_IRI[c.organ] ?? null : null, systemIri: systemIriOf(c.systemKey) ?? null,
    exactMatch: (c.maps ?? []).map((m) => `${HEALTH_NS}concept/${m.system}/${encodeURIComponent(m.code)}`),
  };
}
