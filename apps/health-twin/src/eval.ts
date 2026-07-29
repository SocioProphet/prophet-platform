// Honest benchmark — a real, published number, measuring what this system ACTUALLY does. NOT a MedQA
// score: MedQA measures full multi-step clinical QA, which our coder doesn't attempt, so claiming a
// MedQA number would be dishonest. Instead we measure our real capabilities on a labeled test set:
//   • clinical CODING — precision / recall / F1 (did we assign the right SNOMED/RxNorm/LOINC?)
//   • NEGATION — accuracy (did we get present-vs-absent right?)
//   • VALUE extraction — accuracy (did we pull "148" from "LDL 148"?)
//   • GUIDELINE guidance — do the right guideline sources fire on the twin's numbers?
//   • TWIN DYNAMICS — does the learned RESIDUAL beat the mechanistic model alone, on HELD-OUT subjects?
// Run: `npx tsx src/eval.ts`. Exits non-zero if any metric falls below its floor — so quality is gated.
import { codeText } from './clinical.js';
import { guidance } from './guidelines.js';
import { ground } from './knowledge.js';
import { buildCohort, mechanisticFor, SAMPLE_DAYS, HORIZON_DAYS } from './dynamics/cohort.js';
import { fitSurrogate, proposeDelta } from './dynamics/surrogate.js';
import { OBSERVABLE, type Compartment } from './dynamics/mechanistic.js';

interface Gold { code: string; negated: boolean; value?: string }
interface Case { text: string; gold: Gold[] }

const CASES: Case[] = [
  { text: '55yo with high blood pressure and prediabetes, on lisinopril and metformin. LDL 148, A1c 6.0. Denies chest pain. Knee x-ray no fracture — sprain.',
    gold: [
      { code: '38341003', negated: false }, { code: '714628002', negated: false },
      { code: '29046', negated: false }, { code: '6809', negated: false },
      { code: '13457-7', negated: false, value: '148' }, { code: '4548-4', negated: false, value: '6.0' },
      { code: '29857009', negated: true }, { code: '125605004', negated: true }, { code: '44465007', negated: false },
    ] },
  { text: 'BP 138/85, HR 72. No shortness of breath. Started atorvastatin for high cholesterol.',
    gold: [
      { code: '85354-9', negated: false, value: '138/85' }, { code: '8867-4', negated: false, value: '72' },
      { code: '267036007', negated: true }, { code: '83367', negated: false }, { code: '55822004', negated: false },
    ] },
  { text: 'Type 2 diabetes on metformin and empagliflozin. eGFR 58, creatinine elevated. Reports dizziness, denies headache.',
    gold: [
      { code: '44054006', negated: false }, { code: '6809', negated: false }, { code: '1545653', negated: false },
      { code: '33914-3', negated: false, value: '58' }, { code: '2160-0', negated: false },
      { code: '404640003', negated: false }, { code: '25064002', negated: true },
    ] },
  { text: 'Ruled out MI. Chest pain resolved. Aspirin daily. Afib noted on ECG.',
    gold: [
      { code: '22298006', negated: true }, { code: '29857009', negated: true },
      { code: '1191', negated: false }, { code: '49436004', negated: false },
    ] },
];

function evalCoding() {
  let tp = 0, fp = 0, fn = 0, negRight = 0, negTotal = 0, valRight = 0, valTotal = 0;
  for (const c of CASES) {
    const got = codeText(c.text).entities;
    const goldByCode = new Map(c.gold.map((g) => [g.code, g]));
    const gotByCode = new Map(got.map((e) => [e.code, e]));
    for (const g of c.gold) {
      const e = gotByCode.get(g.code);
      if (e) {
        tp++;
        negTotal++; if (e.negated === g.negated) negRight++;
        if (g.value != null) { valTotal++; if (e.value === g.value) valRight++; }
      } else fn++;
    }
    for (const e of got) if (!goldByCode.has(e.code)) fp++;
  }
  const precision = tp / (tp + fp || 1), recall = tp / (tp + fn || 1);
  const f1 = 2 * precision * recall / (precision + recall || 1);
  return { precision, recall, f1, negAcc: negRight / (negTotal || 1), valAcc: valRight / (valTotal || 1), tp, fp, fn };
}

function evalGuidance() {
  const srcs = new Set(guidance().items.map((i) => i.source));
  const want = ['ACC/AHA 2018 Blood Cholesterol Guideline', 'ADA Standards of Care in Diabetes', 'ACC/AHA 2017 High Blood Pressure Guideline'];
  const hit = want.filter((w) => srcs.has(w));
  return { want: want.length, hit: hit.length, acc: hit.length / want.length };
}

// grounding: does a clinical-knowledge question retrieve the right authoritative source?
function evalGrounding() {
  const cases: { q: string; source: string }[] = [
    { q: 'what does prediabetes mean', source: 'ADA Standards of Care in Diabetes' },
    { q: 'what does a statin do', source: 'Cholesterol Treatment Trialists’ meta-analyses' },
    { q: 'what is my egfr and kidney function', source: 'KDIGO Chronic Kidney Disease Guideline' },
    { q: 'what are blood pressure stages', source: 'ACC/AHA 2017 High Blood Pressure Guideline' },
  ];
  let hit = 0;
  for (const c of cases) { const g = ground(c.q); if (g.grounded && g.citations.some((x) => x.source === c.source)) hit++; }
  return { hit, total: cases.length, acc: hit / cases.length };
}

// twin dynamics: mechanistic-alone vs mechanistic + gated learned residual, on HELD-OUT synthetic
// subjects the surrogate was never fitted on. 🔴 The cohort is SYNTHETIC and its ground truth is a
// superset of the mechanistic model, so this measures that the residual machinery extracts real signal
// from covariates the ODE does not consume. It is NOT clinical validation and must never be quoted as
// such. Renal is expected NOT to improve — see the note by its floor.
function evalDynamics() {
  const sur = fitSurrogate();
  const test = buildCohort().filter((s) => s.split === 'test');
  const out: Record<string, { rmseM: number; rmseR: number; gain: number; n: number }> = {};
  for (const k of ['cardio', 'hepatic', 'renal'] as Compartment[]) {
    let seM = 0, seR = 0, n = 0;
    for (const s of test) {
      const mech = mechanisticFor(s)[k];
      SAMPLE_DAYS.forEach((d, i) => {
        const y = s.truth[k][i]!, m = mech[i]!;
        const r = m + proposeDelta(sur, k, s.covariates, d / HORIZON_DAYS);
        seM += (y - m) ** 2; seR += (y - r) ** 2; n++;
      });
    }
    const rmseM = Math.sqrt(seM / n), rmseR = Math.sqrt(seR / n);
    out[k] = { rmseM, rmseR, gain: 1 - rmseR / rmseM, n };
  }
  return out;
}

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const cod = evalCoding();
const gud = evalGuidance();
const grd = evalGrounding();
const dyn = evalDynamics();

console.log('\n═══ prophet-health clinical eval (honest — NOT MedQA) ═══');
console.log(`  Clinical coding   precision ${pct(cod.precision)} · recall ${pct(cod.recall)} · F1 ${pct(cod.f1)}   (tp ${cod.tp} fp ${cod.fp} fn ${cod.fn})`);
console.log(`  Negation          accuracy  ${pct(cod.negAcc)}`);
console.log(`  Value extraction  accuracy  ${pct(cod.valAcc)}`);
console.log(`  Guideline firing  ${gud.hit}/${gud.want}  ${pct(gud.acc)}`);
console.log(`  Grounding source  ${grd.hit}/${grd.total}  ${pct(grd.acc)}   (right authoritative source cited)`);
console.log('  (measures OUR capabilities — coding/negation/values/guidance/grounding — not full clinical QA)');
console.log('\n  Twin dynamics — held-out RMSE, mechanistic alone → mechanistic + gated learned residual');
for (const k of ['cardio', 'hepatic', 'renal'] as Compartment[]) {
  const d = dyn[k]!;
  console.log(`    ${k.padEnd(8)} ${d.rmseM.toFixed(4)} → ${d.rmseR.toFixed(4)} ${OBSERVABLE[k].unit.padEnd(7)} ${d.gain >= 0 ? pct(d.gain) + ' better' : pct(-d.gain) + ' WORSE'}   (n=${d.n} held-out points)`);
}
console.log('    🔴 SYNTHETIC cohort — measures that the residual extracts signal the ODE ignores, NOT clinical validity.');

// quality floors — the build fails if we regress below these
const floors = { f1: 0.85, negAcc: 0.9, valAcc: 0.9, guidance: 1.0, grounding: 1.0, cardioGain: 0.20, hepaticGain: 0.15, renalNoHarm: -0.02 };
const fails: string[] = [];
if (cod.f1 < floors.f1) fails.push(`F1 ${pct(cod.f1)} < ${pct(floors.f1)}`);
if (cod.negAcc < floors.negAcc) fails.push(`negation ${pct(cod.negAcc)} < ${pct(floors.negAcc)}`);
if (cod.valAcc < floors.valAcc) fails.push(`values ${pct(cod.valAcc)} < ${pct(floors.valAcc)}`);
if (gud.acc < floors.guidance) fails.push(`guidance ${pct(gud.acc)} < ${pct(floors.guidance)}`);
if (grd.acc < floors.grounding) fails.push(`grounding ${pct(grd.acc)} < ${pct(floors.grounding)}`);
if (dyn.cardio!.gain < floors.cardioGain) fails.push(`cardio residual gain ${pct(dyn.cardio!.gain)} < ${pct(floors.cardioGain)}`);
if (dyn.hepatic!.gain < floors.hepaticGain) fails.push(`hepatic residual gain ${pct(dyn.hepatic!.gain)} < ${pct(floors.hepaticGain)}`);
// Renal is floored at NO HARM, not at an improvement. Over a 90-day horizon the albuminuria-driven
// divergence (< 0.5 mL/min) is far below the eGFR assay noise (1.6 mL/min 1σ), so there is nothing to
// learn. That is a property of the observable, and the honest response is to say so in the floor rather
// than to lengthen the horizon or shrink the noise until the number flatters us.
if (dyn.renal!.gain < floors.renalNoHarm) fails.push(`renal residual DEGRADED fit by ${pct(-dyn.renal!.gain)}`);
console.log(fails.length ? `\n✗ below floor: ${fails.join(' · ')}` : '\n✓ all metrics above floor');
process.exit(fails.length ? 1 : 0);
