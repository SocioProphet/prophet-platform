// reference.ts — the professional knowledge layer (surface 8; the doc's biggest section). The key
// move from the doc: store knowledge as STRUCTURED objects rendered differently by AUDIENCE, not as
// articles. Three capabilities: (1) condition cards (red flags / workup / follow-up) with
// patient/clinician/trainee renderers off one source of truth; (2) a medication safety check
// (interactions, allergy conflicts, duplicate therapy); (3) a guideline-DELTA engine (what changed,
// who it affects, confidence, what to do) — the higher-value adaptation of "current awareness".
// Non-diagnostic reference; a clinician decides. Task-first, not article-first.
import { MEDICATIONS, ALLERGIES } from './data.js';

export type Audience = 'patient' | 'clinician' | 'trainee';

interface ConditionKnowledge {
  id: string; name: string; snomed: string;
  redFlags: string[]; workup: string[]; followUp: string[];
  plain: string; clinical: string; teaching: string;
  cites: string[];
}

// Cardiometabolic wedge — the source-of-truth knowledge objects.
const KB: ConditionKnowledge[] = [
  {
    id: 'hypertension', name: 'Essential hypertension', snomed: '38341003',
    redFlags: ['BP ≥180/120 with symptoms (hypertensive emergency)', 'chest pain, breathlessness, or neuro symptoms', 'new vision change'],
    workup: ['confirm with out-of-office readings', 'basic metabolic panel + eGFR', 'lipids + A1c', 'ECG', 'assess 10-yr ASCVD risk'],
    followUp: ['recheck in 2–4 weeks after a change', 'home BP log', 'reinforce lifestyle (sodium, activity, weight, alcohol)'],
    plain: 'High blood pressure usually has no symptoms but, over time, raises the risk of heart and kidney problems. It is very treatable — with lifestyle changes and, if needed, medication. Very high readings with symptoms are an emergency.',
    clinical: 'Confirm with out-of-office measurement before labeling. Stage per ACC/AHA 2017; base drug therapy on stage + ASCVD risk + comorbidity (e.g., ACEi/ARB in CKD or diabetes). Screen for secondary causes when the pattern fits.',
    teaching: 'Teaching points: (1) diagnosis needs repeated, properly-measured readings; (2) the 2017 threshold moved to 130/80; (3) drug choice is comorbidity-driven; (4) know the emergency vs urgency distinction (end-organ signs).',
    cites: ['ACC/AHA 2017 High Blood Pressure Guideline'],
  },
  {
    id: 'prediabetes', name: 'Prediabetes', snomed: '714628002',
    redFlags: ['symptoms of overt diabetes (thirst, urination, weight loss)', 'A1c ≥6.5% on repeat (now diabetes)'],
    workup: ['confirm with A1c or fasting glucose', 'assess cardiometabolic risk factors', 'consider OGTT where indicated'],
    followUp: ['A1c every 6–12 months', 'structured lifestyle / DPP referral', 'consider metformin if high-risk'],
    plain: 'Prediabetes means blood sugar is higher than normal but not yet diabetes. It is a warning sign — and often reversible. Diet, activity, and weight change can bring it back down; your clinician tracks it over time.',
    clinical: 'Per ADA Standards, A1c 5.7–6.4%. Intensive lifestyle intervention is first-line; metformin is reasonable in higher-risk phenotypes (BMI ≥35, age <60, prior GDM). Re-screen at least yearly.',
    teaching: 'Teaching points: (1) A1c bands (normal / prediabetes / diabetes); (2) lifestyle > pharmacotherapy for progression risk; (3) who benefits from metformin; (4) it is a risk state, not a disease label.',
    cites: ['ADA Standards of Care in Diabetes'],
  },
  {
    id: 'hyperlipidemia', name: 'Hyperlipidemia', snomed: '55822004',
    redFlags: ['known ASCVD with an acute presentation', 'signs of familial hypercholesterolemia (very high LDL, xanthomas)'],
    workup: ['fasting or non-fasting lipid panel', '10-yr ASCVD risk estimate', 'assess statin-benefit group'],
    followUp: ['lipids 4–12 weeks after starting/adjusting a statin', 'reinforce adherence + lifestyle'],
    plain: 'High cholesterol (especially LDL) can build up in arteries over years and raise heart-attack and stroke risk. It usually has no symptoms. Statins and lifestyle changes lower it; your clinician decides based on your overall risk.',
    clinical: 'Per ACC/AHA 2018, identify the four statin-benefit groups; use the pooled-cohort ASCVD estimate for primary prevention. Intensity is risk-driven; recheck lipids to confirm response + adherence.',
    teaching: 'Teaching points: (1) the four statin-benefit groups; (2) primary vs secondary prevention; (3) moderate vs high-intensity statins; (4) LDL as the primary target of therapy.',
    cites: ['ACC/AHA 2018 Blood Cholesterol Guideline'],
  },
];

export function conditionList() {
  return KB.map((k) => ({ id: k.id, name: k.name, snomed: k.snomed }));
}

// Render one card FOR an audience off the single source of truth (the doc's core "audience renderer").
export function conditionCard(id: string, audience: Audience = 'patient') {
  const k = KB.find((x) => x.id === id);
  if (!k) return null;
  const base = { id: k.id, name: k.name, snomed: k.snomed, audience, redFlags: k.redFlags };
  const disclaimer = 'Reference information, non-diagnostic. A clinician applies it to the individual.';
  if (audience === 'clinician') return { ...base, framing: k.clinical, workup: k.workup, followUp: k.followUp, citations: k.cites, disclaimer };
  if (audience === 'trainee') return { ...base, framing: k.clinical, teaching: k.teaching, workup: k.workup, followUp: k.followUp, citations: k.cites, disclaimer };
  // patient: plain language + red flags in lay terms; no citations/workup jargon
  return { ...base, framing: k.plain, whatToWatch: k.redFlags, disclaimer };
}

// ── medication safety — delegates to the real drugsafety.ts dataset (curated, RxNorm-aware) ─────────
import { checkDrugSafety, type MedSafetyResult } from './drugsafety.js';
export type MedCheck = MedSafetyResult;

// Check a med list (defaults to the twin's active meds) against the real interaction dataset, the
// twin's allergies (with class cross-reactivity), and duplicate therapy (by drug class). Non-diagnostic.
export function checkMeds(meds?: { display: string }[], allergyDisplays?: string[]): MedCheck {
  const list = meds ?? MEDICATIONS.map((m) => ({ display: m.display }));
  const allergies = allergyDisplays ?? ALLERGIES.map((a) => a.display);
  return checkDrugSafety(list, allergies);
}

// ── guideline-delta engine — actionable deltas, not article pages ─────────────────────────────────
export interface GuidelineDelta {
  id: string; area: string; changed: string; affects: string;
  confidence: 'high' | 'moderate' | 'low'; action: string; date: string; source: string;
}
const DELTAS: GuidelineDelta[] = [
  { id: 'd-htn-2017', area: 'Hypertension', changed: 'Stage-1 threshold lowered to 130/80', affects: 'adults being screened/treated for BP', confidence: 'high', action: 'Re-band existing patients; base therapy on stage + ASCVD risk.', date: '2017-11-13', source: 'ACC/AHA 2017 High Blood Pressure Guideline' },
  { id: 'd-lipid-2018', area: 'Lipids', changed: 'Risk-enhancing factors + selective CAC to refine borderline/intermediate risk', affects: 'primary-prevention statin decisions', confidence: 'high', action: 'Use enhancers/CAC when the ASCVD estimate is borderline.', date: '2018-11-10', source: 'ACC/AHA 2018 Blood Cholesterol Guideline' },
  { id: 'd-dm-annual', area: 'Diabetes', changed: 'Standards of Care refreshed annually', affects: 'screening, targets, and therapy sequencing', confidence: 'moderate', action: 'Re-check the current year Standards before setting targets.', date: '2026-01-01', source: 'ADA Standards of Care in Diabetes' },
];
export function guidelineDeltas(area?: string): { deltas: GuidelineDelta[]; disclaimer: string } {
  const deltas = area ? DELTAS.filter((d) => d.area.toLowerCase() === area.toLowerCase()) : DELTAS;
  return { deltas, disclaimer: 'Guideline deltas are informational and should be verified against the current primary source before changing care.' };
}
