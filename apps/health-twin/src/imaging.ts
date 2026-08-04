// imaging.ts — the imaging & document agent (verb 1 Observe + 4 Explain; use case #3). Takes the
// TEXT of a radiology / pathology / discharge report and returns a plain-language explanation: the
// modality + body site, the structured findings, what the terms mean, what usually comes next, and
// the follow-up questions that matter — grounded in the medical brain. A CRITICAL-finding floor
// mirrors triage: an urgent term ("acute", "hemorrhage", "mass", "fracture") raises urgency +
// escalate regardless of anything reassuring. NON-DIAGNOSTIC: it explains a report a clinician
// authored; it does not read pixels and does not diagnose. (DICOM pixel analysis is a later tranche.)
import { codeText } from './clinical.js';
import { ground, groundFromBrain, type Grounded } from './knowledge.js';
import type { Urgency } from './triage.js';

const MODALITIES: { any: string[]; modality: string }[] = [
  { any: ['x-ray', 'radiograph', 'xr ', 'plain film'], modality: 'X-ray' },
  { any: ['mri', 'magnetic resonance'], modality: 'MRI' },
  { any: ['ct ', 'computed tomography', 'cat scan'], modality: 'CT' },
  { any: ['ultrasound', 'sonograph', 'echocardiog'], modality: 'Ultrasound' },
  { any: ['pathology', 'biopsy', 'histolog', 'cytolog'], modality: 'Pathology' },
  { any: ['discharge', 'after visit', 'aftercare'], modality: 'Discharge summary' },
];
const BODY_SITES = ['chest', 'head', 'brain', 'abdomen', 'pelvis', 'knee', 'shoulder', 'spine', 'lumbar', 'cervical', 'wrist', 'ankle', 'hip', 'lung', 'liver', 'kidney', 'breast'];

// Critical imaging/report terms → escalate. Negation-aware so "no acute" / "no evidence of
// hemorrhage" does NOT trip. Safety-first: this errs toward flagging for a clinician read.
const CRITICAL: { any: string[]; reason: string }[] = [
  { any: ['hemorrhage', 'haemorrhage', 'bleed', 'hematoma'], reason: 'possible bleeding' },
  { any: ['mass', 'tumor', 'tumour', 'malignan', 'neoplas', 'lesion suspicious', 'suspicious for'], reason: 'a finding that needs prompt work-up' },
  { any: ['fracture', 'displaced', 'dislocation'], reason: 'possible fracture/dislocation' },
  { any: ['acute', 'embolism', 'embolus', 'infarct', 'ischemi', 'aneurysm', 'perforation', 'obstruction', 'pneumothorax'], reason: 'possible acute process' },
  { any: ['metasta'], reason: 'a finding that needs prompt work-up' },
];

const NEG = /\b(no|not|without|negative for|no evidence of|absent|unremarkable|resolved|ruled out)\b/;
function present(lower: string, phrase: string): boolean {
  let idx = lower.indexOf(phrase);
  while (idx !== -1) {
    const start = Math.max(lower.lastIndexOf('.', idx), lower.lastIndexOf(',', idx), lower.lastIndexOf(';', idx), lower.lastIndexOf(':', idx)) + 1;
    if (!NEG.test(lower.slice(start, idx))) return true;
    idx = lower.indexOf(phrase, idx + phrase.length);
  }
  return false;
}
const firstMatch = (lower: string, opts: { any: string[]; [k: string]: any }[]) => opts.find((o) => o.any.some((p) => lower.includes(p)));

export interface ImagingReading {
  modality: string;
  bodySite: string;
  findings: string[];                 // structured terms extracted from the report
  criticalFlags: { term: string; reason: string }[];
  urgency: Urgency;                    // routine unless a critical term floors it to urgent/emergency
  escalate: boolean;
  plainLanguage: string;              // what the report is saying, in plain words
  whatComesNext: string;
  followUpQuestions: string[];
  grounded: boolean;
  evidence?: string;
  citations: { source: string; tier: string }[];
  disclaimer: string;
}

export async function interpretReport(reportText: string): Promise<ImagingReading> {
  const text = (reportText ?? '').trim();
  const lower = text.toLowerCase();

  const modality = firstMatch(lower, MODALITIES)?.modality ?? 'Report';
  const bodySite = BODY_SITES.find((s) => lower.includes(s)) ?? 'unspecified';

  const coded = codeText(text);
  const findings = [...new Set(coded.entities.filter((e) => !e.negated).map((e) => e.display))];

  // critical-finding floor (negation-aware)
  const criticalFlags: { term: string; reason: string }[] = [];
  for (const c of CRITICAL) for (const p of c.any) if (present(lower, p)) { criticalFlags.push({ term: p, reason: c.reason }); break; }

  let urgency: Urgency = 'routine';
  if (criticalFlags.some((f) => /bleeding|acute process/.test(f.reason))) urgency = 'emergency';
  else if (criticalFlags.length) urgency = 'urgent';
  const escalate = criticalFlags.length > 0;

  // ground the primary finding for a plain-language explanation
  const term = findings[0] ?? bodySite;
  let g: Grounded | null = null;
  try { g = (await groundFromBrain(`what does ${term} mean on a ${modality} report and what is the usual follow-up`)) ?? ground(term); }
  catch { g = ground(term); }

  const plainLanguage = criticalFlags.length
    ? `This ${modality.toLowerCase()} of the ${bodySite} contains term(s) that a clinician should review promptly (${criticalFlags.map((f) => f.reason).join('; ')}). It does not confirm a diagnosis — the reading clinician decides.`
    : findings.length
      ? `This ${modality.toLowerCase()} of the ${bodySite} mentions: ${findings.join(', ')}. In plain terms, these are the items the reader noted; most reports pair findings with an "impression" that says how significant they are.`
      : `This appears to be a ${modality.toLowerCase()} of the ${bodySite}. No standout critical terms were detected in the text, but the reading clinician's impression is what matters.`;

  const whatComesNext = urgency === 'emergency'
    ? 'A finding like this is usually acted on quickly — contact the ordering clinician or seek care now if you have symptoms.'
    : urgency === 'urgent'
      ? 'This usually prompts a timely follow-up conversation with the ordering clinician.'
      : 'The usual next step is to review the impression with the ordering clinician, who decides on any follow-up imaging or referral.';

  return {
    modality, bodySite, findings, criticalFlags, urgency, escalate,
    plainLanguage, whatComesNext,
    followUpQuestions: [
      'What did the impression / conclusion section say?',
      'Do you have symptoms related to this area right now?',
      'Who ordered this study, and do you have a follow-up scheduled?',
    ],
    grounded: !!g?.grounded,
    evidence: g?.grounded ? g.answer : undefined,
    citations: (g?.citations ?? []).map((c) => ({ source: c.source, tier: c.tier })),
    disclaimer: 'Plain-language explanation of a report a clinician authored — informational, non-diagnostic, and not a substitute for the reading clinician\'s interpretation. It does not analyze the images themselves.',
  };
}
