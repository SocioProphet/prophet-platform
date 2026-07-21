// Honest benchmark — a real, published number, measuring what this system ACTUALLY does. NOT a MedQA
// score: MedQA measures full multi-step clinical QA, which our coder doesn't attempt, so claiming a
// MedQA number would be dishonest. Instead we measure our real capabilities on a labeled test set:
//   • clinical CODING — precision / recall / F1 (did we assign the right SNOMED/RxNorm/LOINC?)
//   • NEGATION — accuracy (did we get present-vs-absent right?)
//   • VALUE extraction — accuracy (did we pull "148" from "LDL 148"?)
//   • GUIDELINE guidance — do the right guideline sources fire on the twin's numbers?
// Run: `npx tsx src/eval.ts`. Exits non-zero if any metric falls below its floor — so quality is gated.
import { codeText } from './clinical.js';
import { guidance } from './guidelines.js';

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

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const cod = evalCoding();
const gud = evalGuidance();

console.log('\n═══ prophet-health clinical eval (honest — NOT MedQA) ═══');
console.log(`  Clinical coding   precision ${pct(cod.precision)} · recall ${pct(cod.recall)} · F1 ${pct(cod.f1)}   (tp ${cod.tp} fp ${cod.fp} fn ${cod.fn})`);
console.log(`  Negation          accuracy  ${pct(cod.negAcc)}`);
console.log(`  Value extraction  accuracy  ${pct(cod.valAcc)}`);
console.log(`  Guideline firing  ${gud.hit}/${gud.want}  ${pct(gud.acc)}`);
console.log('  (measures OUR capabilities — coding/negation/values/guidance — not full clinical QA)');

// quality floors — the build fails if we regress below these
const floors = { f1: 0.85, negAcc: 0.9, valAcc: 0.9, guidance: 1.0 };
const fails: string[] = [];
if (cod.f1 < floors.f1) fails.push(`F1 ${pct(cod.f1)} < ${pct(floors.f1)}`);
if (cod.negAcc < floors.negAcc) fails.push(`negation ${pct(cod.negAcc)} < ${pct(floors.negAcc)}`);
if (cod.valAcc < floors.valAcc) fails.push(`values ${pct(cod.valAcc)} < ${pct(floors.valAcc)}`);
if (gud.acc < floors.guidance) fails.push(`guidance ${pct(gud.acc)} < ${pct(floors.guidance)}`);
console.log(fails.length ? `\n✗ below floor: ${fails.join(' · ')}` : '\n✓ all metrics above floor');
process.exit(fails.length ? 1 : 0);
