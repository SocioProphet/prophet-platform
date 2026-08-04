// triage.ts — the agentic OOD loop for medical triage, native. An input passes through
// PERCEIVE (structure the described symptoms) → REASON (red flags + urgency band) → ACT (retrieve
// grounding) → VERIFY (a red-flag SAFETY FLOOR + an Abstain gate), yielding a disposition of act /
// abstain / escalate. This is verbs 3 (Reason), 5 (Route hand-off) and 9 (Escalate) of the thesis
// and a working instantiation of the unified agentic OOD framework (Perceive/Reason/Act/Verify with
// Abstain + Escalate).
//
// NON-DIAGNOSTIC. It bands urgency, surfaces danger signs, asks the next-best question, and routes
// the level of care — it does not diagnose. The safety contract, enforced in invariants.ts: a
// detected (non-negated) red flag can NEVER resolve below emergency, and never to self-care.
import { codeText } from './clinical.js';
import { ground, groundFromBrain, type Grounded } from './knowledge.js';

export type Urgency = 'self-care' | 'monitor' | 'routine' | 'urgent' | 'emergency';
export type Disposition = 'act' | 'abstain' | 'escalate';

export const URGENCY_RANK: Record<Urgency, number> = {
  'self-care': 0, monitor: 1, routine: 2, urgent: 3, emergency: 4,
};

// Red flags — emergency patterns. Each carries the phrases that trip it and the escalation reason.
// Matching is negation-aware, so "no chest pain" / "denies chest pain" does NOT trip the flag.
// Safety-first: this list deliberately errs toward escalation.
interface RedFlag { id: string; any: string[]; reason: string }
const RED_FLAGS: RedFlag[] = [
  { id: 'cardiac', any: ['chest pain', 'chest pressure', 'chest tightness', 'radiating to arm', 'radiating to my arm', 'radiating to jaw', 'crushing chest'], reason: 'possible cardiac event' },
  { id: 'stroke', any: ['face drooping', 'facial droop', 'arm weakness', 'slurred speech', 'trouble speaking', 'sudden numbness', 'sudden confusion', 'sudden vision loss', 'one side of my body'], reason: 'possible stroke (FAST)' },
  { id: 'airway', any: ['difficulty breathing', 'trouble breathing', 'shortness of breath', "can't breathe", 'cannot breathe', 'throat swelling', 'tongue swelling', 'gasping'], reason: 'possible airway/breathing compromise' },
  { id: 'anaphylaxis', any: ['anaphylaxis', 'throat closing', 'lips swelling', 'swelling of lips', 'hives all over'], reason: 'possible anaphylaxis' },
  { id: 'hemorrhage', any: ['uncontrolled bleeding', 'heavy bleeding', "won't stop bleeding", 'coughing up blood', 'vomiting blood', 'blood in stool', 'black stool', 'bleeding heavily'], reason: 'possible major bleeding' },
  { id: 'neuro', any: ['worst headache', 'worst headache of my life', 'sudden severe headache', 'thunderclap headache', 'seizure', 'unresponsive', 'loss of consciousness', 'fainted', 'passed out', 'blacked out'], reason: 'possible neurological emergency' },
  { id: 'sepsis', any: ['fever with confusion', 'fever and confusion', 'stiff neck with fever', 'confused and feverish'], reason: 'possible serious infection / sepsis' },
  { id: 'mental-health', any: ['suicidal', 'kill myself', 'want to die', 'end my life', 'hurt myself', 'harm myself'], reason: 'mental-health emergency' },
  { id: 'obstetric', any: ['pregnant and bleeding', 'bleeding and pregnant', 'severe abdominal pain pregnant'], reason: 'possible obstetric emergency' },
  { id: 'neurovascular', any: ['cold and blue', 'no pulse in', 'limb is cold', 'numb and cold'], reason: 'possible neurovascular compromise' },
];

// Sub-emergency urgency signals — raise the band without being red-flag-critical. Ordered so the
// most acute wins (the loop takes the MAX band across all matched signals).
interface UrgencySignal { any: string[]; urgency: Urgency }
const SIGNALS: UrgencySignal[] = [
  { any: ['spreading redness', 'red streaks', 'pus', 'wound is warm', 'getting worse fast', 'high fever'], urgency: 'urgent' },
  { any: ['persistent vomiting', "can't keep fluids down", 'severe pain', 'dehydrated', 'severe'], urgency: 'urgent' },
  { any: ['fever', 'vomiting', 'diarrhea', 'rash', 'swelling', 'sprain', 'cough', 'sore throat', 'headache', 'infected', 'pain'], urgency: 'routine' },
  { any: ['mild', 'minor', 'small cut', 'scrape', 'slight'], urgency: 'monitor' },
];

const NEG = /\b(no|not|without|denies|denied|never|negative for|ruled out|rule out|resolved|no longer)\b/;

// negation-aware phrase presence: the phrase appears and is not preceded, within its clause, by a
// negation trigger. Clause = bounded by sentence/clause breaks so a negation in a prior clause
// ("no fever, but chest pain") does not cancel a later phrase.
function present(lower: string, phrase: string): boolean {
  let idx = lower.indexOf(phrase);
  while (idx !== -1) {
    const clauseStart = Math.max(
      lower.lastIndexOf('.', idx), lower.lastIndexOf(',', idx),
      lower.lastIndexOf(';', idx), lower.lastIndexOf(' but ', idx),
    ) + 1;
    if (!NEG.test(lower.slice(clauseStart, idx))) return true;
    idx = lower.indexOf(phrase, idx + phrase.length);
  }
  return false;
}

export interface TriageStep { step: 'perceive' | 'reason' | 'act' | 'verify'; note: string }
export interface TriageResult {
  complaint: string;
  perceived: string[];                 // structured findings (non-negated), from clinical NER
  redFlags: { id: string; reason: string }[];
  urgency: Urgency;
  disposition: Disposition;            // act | abstain | escalate
  care: string;                        // plain-language action for the person
  nextBestQuestions: string[];         // when Abstaining: the highest-information questions to ask
  grounded: boolean;
  evidence?: string;
  citations: { source: string; tier: string }[];
  loop: TriageStep[];                  // the Perceive→Reason→Act→Verify trace, auditable
  rationale: string;
  disclaimer: string;
}

const CARE_LINE: Record<Urgency, string> = {
  emergency: 'Call emergency services (in the US, 911) or go to the nearest emergency department now.',
  urgent: 'Seek urgent care within the next few hours (urgent-care clinic or, if unavailable, the ED).',
  routine: 'Schedule a primary-care visit in the next few days.',
  monitor: 'Reasonable to monitor at home; re-check if it changes or does not improve.',
  'self-care': 'Reasonable to self-care and watch; seek care if anything worsens.',
};

export async function triage(complaint: string, _context?: unknown): Promise<TriageResult> {
  const text = (complaint ?? '').trim();
  const lower = text.toLowerCase();
  const loop: TriageStep[] = [];

  // 1. PERCEIVE — structure the described symptoms (clinical NER, negation-aware).
  const coded = codeText(text);
  const perceived = [...new Set(coded.entities.filter((e) => !e.negated).map((e) => e.display))];
  const missing: string[] = [];
  if (text && !/\b(day|days|week|weeks|hour|hours|since|ago|minutes?|today|yesterday)\b/.test(lower)) missing.push('how long this has been going on');
  if (text && !/\b(mild|moderate|severe|slight|bad|worst|minor|\d+\s*\/\s*10)\b/.test(lower)) missing.push('how severe it is (mild, moderate, or severe)');
  loop.push({ step: 'perceive', note: `structured ${perceived.length} finding(s); ${missing.length} key detail(s) missing` });

  // 2. REASON — red flags + urgency band (take the MAX band across matched signals).
  const redFlags = RED_FLAGS.filter((rf) => rf.any.some((p) => present(lower, p))).map((rf) => ({ id: rf.id, reason: rf.reason }));
  let urgency: Urgency = 'self-care';
  for (const s of SIGNALS) if (s.any.some((p) => present(lower, p)) && URGENCY_RANK[s.urgency] > URGENCY_RANK[urgency]) urgency = s.urgency;
  loop.push({ step: 'reason', note: `${redFlags.length} red flag(s); provisional urgency=${urgency}` });

  // 3. ACT — retrieve grounding for the cluster (brain → local KB), the paper's Retrieve action.
  const term = perceived[0] ?? (text.split(/[.,;\n]/)[0] || 'symptom').trim();
  let g: Grounded | null = null;
  try { g = (await groundFromBrain(`clinical evaluation and management of ${term}`)) ?? ground(term); } catch { g = ground(term); }
  loop.push({ step: 'act', note: g?.grounded ? `grounded via ${g.retrieval}` : 'no grounding found' });

  // 4. VERIFY — the SAFETY FLOOR + the Abstain gate.
  //   FLOOR: any detected red flag forces emergency + escalate. It can never resolve to self-care.
  //   ABSTAIN: if the picture is too thin to band safely AND it is not already an emergency, don't
  //   guess — ask the next-best question (the paper's Abstain, the doc's "ask for missing info").
  let disposition: Disposition = 'act';
  const nextBestQuestions: string[] = [];
  if (redFlags.length) { urgency = 'emergency'; disposition = 'escalate'; }
  else if (perceived.length === 0 || missing.length >= 2) {
    disposition = 'abstain';
    if (perceived.length === 0) nextBestQuestions.push('What is the main symptom or problem you are noticing?');
    nextBestQuestions.push(...missing.map((m) => `Can you tell me ${m}?`));
  }
  loop.push({ step: 'verify', note: `floor applied; urgency=${urgency}; disposition=${disposition}` });

  const rationale = redFlags.length
    ? `Escalating because of danger sign(s): ${redFlags.map((r) => r.reason).join('; ')}. A red flag is treated as an emergency regardless of anything reassuring in the description.`
    : disposition === 'abstain'
      ? 'Not enough detail to band urgency safely — asking the next-best question rather than guessing.'
      : `Banded ${urgency} from the described features; no emergency danger signs detected. This is triage guidance, not a diagnosis.`;

  return {
    complaint: text,
    perceived, redFlags, urgency, disposition,
    care: CARE_LINE[urgency],
    nextBestQuestions,
    grounded: !!g?.grounded,
    evidence: g?.grounded ? g.answer : undefined,
    citations: (g?.citations ?? []).map((c) => ({ source: c.source, tier: c.tier })),
    loop,
    rationale,
    disclaimer: 'Triage guidance only — not a diagnosis and not a substitute for professional care. When in doubt, or if anything worsens, seek in-person care. In an emergency call your local emergency number.',
  };
}
