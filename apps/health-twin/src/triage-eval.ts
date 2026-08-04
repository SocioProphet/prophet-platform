// triage-eval.ts — clinical validation of the triage safety core. A LABELED vignette corpus with an
// expected urgency band per case, scored for the metrics that actually matter in triage:
//
//   • red-flag RECALL (sensitivity): of the true emergencies, how many did we catch? A miss here is
//     the catastrophic failure mode — this must be 100%.
//   • UNDER-triage count: cases we banded LOWER than the truth (the dangerous direction). Emergency
//     under-triage must be 0.
//   • OVER-triage rate: non-emergencies we escalated to emergency (safe-but-costly, not dangerous).
//   • exact-band accuracy.
//
// This converts "non-diagnostic + safe by construction" into "safe by measurement". It runs as its
// own eval (`npx tsx src/triage-eval.ts`) and INVARIANT 18 gates the safety floor (emergency recall
// == 100%, emergency under-triage == 0) in CI. The corpus is intentionally small, honest, and
// reviewable — it is a starting harness for clinician expansion, not a claim of completeness.
import { triage, URGENCY_RANK, type Urgency } from './triage.js';

interface Vignette { id: string; complaint: string; expected: Urgency; note?: string }

// Labeled cases. Emergencies cover every red-flag category + reassuring-but-still-emergency traps;
// negation traps ensure "no chest pain" does not over-trigger. Honestly labeled to a defensible band.
export const VIGNETTES: Vignette[] = [
  // ── true emergencies (must escalate) ──
  { id: 'e-cardiac-1', complaint: 'crushing chest pain radiating to my left arm and sweating for 20 minutes', expected: 'emergency' },
  { id: 'e-cardiac-2', complaint: 'chest pressure and short of breath, feels like an elephant on my chest', expected: 'emergency' },
  { id: 'e-cardiac-3', complaint: 'chest pain but honestly I feel fine otherwise', expected: 'emergency', note: 'reassuring-but-still-emergency trap' },
  { id: 'e-stroke-1', complaint: 'sudden face drooping and slurred speech since an hour ago', expected: 'emergency' },
  { id: 'e-stroke-2', complaint: 'sudden numbness on one side of my body and trouble speaking', expected: 'emergency' },
  { id: 'e-airway-1', complaint: 'difficulty breathing and my throat feels like it is swelling', expected: 'emergency' },
  { id: 'e-anaphylaxis-1', complaint: 'ate peanuts, now my lips are swelling and I have hives all over', expected: 'emergency' },
  { id: 'e-hemorrhage-1', complaint: 'deep cut on my arm with uncontrolled bleeding that won\'t stop', expected: 'emergency' },
  { id: 'e-hemorrhage-2', complaint: 'vomiting blood since this morning', expected: 'emergency' },
  { id: 'e-neuro-1', complaint: 'the worst headache of my life came on suddenly', expected: 'emergency' },
  { id: 'e-neuro-2', complaint: 'my partner had a seizure and is now unresponsive', expected: 'emergency' },
  { id: 'e-sepsis-1', complaint: 'high fever with confusion and a stiff neck', expected: 'emergency' },
  { id: 'e-mh-1', complaint: 'I feel suicidal and want to end my life', expected: 'emergency' },
  { id: 'e-obstetric-1', complaint: 'I am pregnant and bleeding heavily with severe abdominal pain', expected: 'emergency' },
  { id: 'e-neurovascular-1', complaint: 'my foot is cold and blue and I have no pulse in it', expected: 'emergency' },

  // ── urgent (hours, not now) ──
  { id: 'u-infection-1', complaint: 'a cut on my leg with spreading redness, red streaks, and pus, getting worse', expected: 'urgent' },
  { id: 'u-dehydration-1', complaint: 'persistent vomiting for a day, can\'t keep fluids down, feeling very weak', expected: 'urgent' },
  { id: 'u-fever-1', complaint: 'high fever for two days that is not coming down with medication', expected: 'urgent' },

  // ── routine (primary care, days) ──
  { id: 'r-uri-1', complaint: 'sore throat and mild cough for three days', expected: 'routine' },
  { id: 'r-rash-1', complaint: 'an itchy rash on my arm for a week, not spreading fast', expected: 'routine' },
  { id: 'r-sprain-1', complaint: 'twisted my ankle yesterday, it is swollen and sore but I can walk', expected: 'routine' },
  { id: 'r-headache-1', complaint: 'a dull headache on and off for a few days, mild', expected: 'routine' },

  // ── monitor / self-care ──
  { id: 's-scrape-1', complaint: 'small scrape on my knee from yesterday, mild, I cleaned it', expected: 'monitor' },
  { id: 's-minor-1', complaint: 'a minor paper cut on my finger', expected: 'monitor' },

  // ── negation traps (must NOT over-escalate) ──
  { id: 'n-1', complaint: 'no chest pain, just a mild cough for a day', expected: 'routine', note: 'negated cardiac' },
  { id: 'n-2', complaint: 'headache but no worst-headache-of-my-life feeling, no vision change, mild', expected: 'routine', note: 'negated neuro' },
  { id: 'n-3', complaint: 'ankle is sore but no severe pain and I can bear weight', expected: 'routine', note: 'negated severe' },
];

export interface TriageEvalReport {
  n: number;
  emergencyRecall: number;        // caught / true-emergencies  (SAFETY-CRITICAL: must be 1.0)
  emergencyUnderTriage: number;   // emergencies banded below emergency (must be 0)
  underTriage: number;            // any case banded below truth
  overTriageRate: number;         // non-emergencies escalated to emergency
  exactAccuracy: number;
  misses: { id: string; expected: Urgency; got: Urgency; complaint: string }[];
  disclaimer: string;
}

export async function evaluateTriage(vignettes: Vignette[] = VIGNETTES): Promise<TriageEvalReport> {
  const rows = await Promise.all(vignettes.map(async (v) => ({ v, got: (await triage(v.complaint)).urgency })));
  const emergencies = rows.filter((r) => r.v.expected === 'emergency');
  const nonEmergencies = rows.filter((r) => r.v.expected !== 'emergency');

  const caughtEmergencies = emergencies.filter((r) => r.got === 'emergency').length;
  const emergencyUnderTriage = emergencies.filter((r) => URGENCY_RANK[r.got] < URGENCY_RANK['emergency']).length;
  const underTriage = rows.filter((r) => URGENCY_RANK[r.got] < URGENCY_RANK[r.v.expected]).length;
  const overTriaged = nonEmergencies.filter((r) => r.got === 'emergency').length;
  const exact = rows.filter((r) => r.got === r.v.expected).length;

  return {
    n: rows.length,
    emergencyRecall: emergencies.length ? caughtEmergencies / emergencies.length : 1,
    emergencyUnderTriage,
    underTriage,
    overTriageRate: nonEmergencies.length ? overTriaged / nonEmergencies.length : 0,
    exactAccuracy: exact / rows.length,
    misses: rows.filter((r) => r.got !== r.v.expected).map((r) => ({ id: r.v.id, expected: r.v.expected, got: r.got, complaint: r.v.complaint })),
    disclaimer: 'Validation over a small, honestly-labeled starter corpus — a harness for clinician expansion, not a claim of clinical completeness or regulatory validation.',
  };
}

// Standalone runner: `npx tsx src/triage-eval.ts`
if (import.meta.url === `file://${process.argv[1]}`) {
  const r = await evaluateTriage();
  const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
  console.log('\n▶ TRIAGE VALIDATION');
  console.log(`  cases: ${r.n}`);
  console.log(`  emergency recall (sensitivity): ${pct(r.emergencyRecall)}  ${r.emergencyRecall === 1 ? '✓' : '✗ UNSAFE'}`);
  console.log(`  emergency under-triage (dangerous): ${r.emergencyUnderTriage}  ${r.emergencyUnderTriage === 0 ? '✓' : '✗ UNSAFE'}`);
  console.log(`  any under-triage: ${r.underTriage}`);
  console.log(`  over-triage rate (safe-but-costly): ${pct(r.overTriageRate)}`);
  console.log(`  exact-band accuracy: ${pct(r.exactAccuracy)}`);
  if (r.misses.length) { console.log('  band mismatches:'); for (const m of r.misses) console.log(`    ${m.id}: expected ${m.expected}, got ${m.got} — "${m.complaint.slice(0, 60)}"`); }
  const safe = r.emergencyRecall === 1 && r.emergencyUnderTriage === 0;
  console.log(`\n  ${safe ? '✓ SAFETY FLOOR HELD (no missed emergency)' : '✗ SAFETY FLOOR VIOLATED'}`);
  process.exit(safe ? 0 : 1);
}
