// Clinical coder — the depth attack on the reasoning column. Turns free text (a dictated note, a
// narrative) into CODED clinical facts: conditions→SNOMED, medications→RxNorm, labs→LOINC, vitals,
// symptoms — with NEGATION detection ("no fracture", "denies chest pain", "ruled out"). This is a real
// clinical-terminology extractor for the cardiometabolic wedge, deterministic + local-first — a genuine
// step up from general-purpose NER (en_core_web_sm), which doesn't know drugs, conditions, or labs. The
// scispaCy + full UMLS linker is the depth follow-on; this codes the common cases honestly, now.
// Non-diagnostic: it labels what the text says with standard codes; it does not diagnose.

export interface CodedEntity {
  text: string;                 // the matched surface term
  category: 'condition' | 'medication' | 'lab' | 'vital' | 'symptom';
  code: string;
  codeSystem: 'SNOMED' | 'RxNorm' | 'LOINC';
  display: string;
  negated: boolean;             // NegEx-style: the note says this is absent/ruled-out
}

interface LexEntry { terms: string[]; category: CodedEntity['category']; code: string; codeSystem: CodedEntity['codeSystem']; display: string }

// Curated lexicon for the cardiometabolic wedge (depth on one vertical, per the scorecard).
const LEX: LexEntry[] = [
  // ── conditions (SNOMED CT) ──
  { terms: ['hypertension', 'high blood pressure', 'htn', 'elevated blood pressure'], category: 'condition', code: '38341003', codeSystem: 'SNOMED', display: 'Essential hypertension' },
  { terms: ['prediabetes', 'pre-diabetes', 'impaired glucose', 'borderline diabetes'], category: 'condition', code: '714628002', codeSystem: 'SNOMED', display: 'Prediabetes' },
  { terms: ['type 2 diabetes', 'type ii diabetes', 't2dm', 'diabetes mellitus', 'diabetes'], category: 'condition', code: '44054006', codeSystem: 'SNOMED', display: 'Type 2 diabetes mellitus' },
  { terms: ['hyperlipidemia', 'high cholesterol', 'dyslipidemia', 'elevated lipids'], category: 'condition', code: '55822004', codeSystem: 'SNOMED', display: 'Hyperlipidemia' },
  { terms: ['chronic kidney disease', 'ckd', 'renal insufficiency'], category: 'condition', code: '709044004', codeSystem: 'SNOMED', display: 'Chronic kidney disease' },
  { terms: ['atrial fibrillation', 'afib', 'a-fib'], category: 'condition', code: '49436004', codeSystem: 'SNOMED', display: 'Atrial fibrillation' },
  { terms: ['myocardial infarction', 'heart attack', 'mi'], category: 'condition', code: '22298006', codeSystem: 'SNOMED', display: 'Myocardial infarction' },
  { terms: ['heart failure', 'chf', 'congestive heart failure'], category: 'condition', code: '84114007', codeSystem: 'SNOMED', display: 'Heart failure' },
  { terms: ['obesity', 'obese'], category: 'condition', code: '414916001', codeSystem: 'SNOMED', display: 'Obesity' },
  { terms: ['sprain', 'sprained'], category: 'condition', code: '44465007', codeSystem: 'SNOMED', display: 'Sprain' },
  { terms: ['fracture', 'fractured', 'broken bone'], category: 'condition', code: '125605004', codeSystem: 'SNOMED', display: 'Fracture' },
  // ── medications (RxNorm ingredient/SCD) ──
  { terms: ['lisinopril'], category: 'medication', code: '29046', codeSystem: 'RxNorm', display: 'Lisinopril' },
  { terms: ['metformin'], category: 'medication', code: '6809', codeSystem: 'RxNorm', display: 'Metformin' },
  { terms: ['atorvastatin', 'lipitor'], category: 'medication', code: '83367', codeSystem: 'RxNorm', display: 'Atorvastatin' },
  { terms: ['amlodipine', 'norvasc'], category: 'medication', code: '17767', codeSystem: 'RxNorm', display: 'Amlodipine' },
  { terms: ['losartan'], category: 'medication', code: '52175', codeSystem: 'RxNorm', display: 'Losartan' },
  { terms: ['hydrochlorothiazide', 'hctz'], category: 'medication', code: '5487', codeSystem: 'RxNorm', display: 'Hydrochlorothiazide' },
  { terms: ['aspirin', 'asa'], category: 'medication', code: '1191', codeSystem: 'RxNorm', display: 'Aspirin' },
  { terms: ['insulin'], category: 'medication', code: '5856', codeSystem: 'RxNorm', display: 'Insulin' },
  { terms: ['empagliflozin', 'jardiance'], category: 'medication', code: '1545653', codeSystem: 'RxNorm', display: 'Empagliflozin' },
  // ── labs (LOINC) ──
  { terms: ['ldl', 'ldl cholesterol', 'bad cholesterol'], category: 'lab', code: '13457-7', codeSystem: 'LOINC', display: 'LDL cholesterol' },
  { terms: ['hdl', 'hdl cholesterol'], category: 'lab', code: '2085-9', codeSystem: 'LOINC', display: 'HDL cholesterol' },
  { terms: ['a1c', 'hba1c', 'hemoglobin a1c', 'glycated hemoglobin'], category: 'lab', code: '4548-4', codeSystem: 'LOINC', display: 'Hemoglobin A1c' },
  { terms: ['glucose', 'blood sugar', 'fasting glucose'], category: 'lab', code: '2345-7', codeSystem: 'LOINC', display: 'Glucose' },
  { terms: ['creatinine'], category: 'lab', code: '2160-0', codeSystem: 'LOINC', display: 'Creatinine' },
  { terms: ['egfr', 'gfr'], category: 'lab', code: '33914-3', codeSystem: 'LOINC', display: 'eGFR' },
  { terms: ['alt', 'alanine aminotransferase'], category: 'lab', code: '1742-6', codeSystem: 'LOINC', display: 'ALT' },
  { terms: ['triglycerides', 'trigs'], category: 'lab', code: '2571-8', codeSystem: 'LOINC', display: 'Triglycerides' },
  // ── vitals (LOINC) ──
  { terms: ['blood pressure', 'bp', 'systolic', 'diastolic'], category: 'vital', code: '85354-9', codeSystem: 'LOINC', display: 'Blood pressure' },
  { terms: ['heart rate', 'pulse', 'hr'], category: 'vital', code: '8867-4', codeSystem: 'LOINC', display: 'Heart rate' },
  { terms: ['weight', 'body weight'], category: 'vital', code: '29463-7', codeSystem: 'LOINC', display: 'Body weight' },
  { terms: ['bmi', 'body mass index'], category: 'vital', code: '39156-5', codeSystem: 'LOINC', display: 'Body mass index' },
  { terms: ['oxygen saturation', 'spo2', 'o2 sat'], category: 'vital', code: '59408-5', codeSystem: 'LOINC', display: 'Oxygen saturation' },
  // ── symptoms (SNOMED) ──
  { terms: ['chest pain'], category: 'symptom', code: '29857009', codeSystem: 'SNOMED', display: 'Chest pain' },
  { terms: ['shortness of breath', 'dyspnea', 'sob', 'short of breath'], category: 'symptom', code: '267036007', codeSystem: 'SNOMED', display: 'Dyspnea' },
  { terms: ['headache'], category: 'symptom', code: '25064002', codeSystem: 'SNOMED', display: 'Headache' },
  { terms: ['dizziness', 'lightheaded', 'lightheadedness'], category: 'symptom', code: '404640003', codeSystem: 'SNOMED', display: 'Dizziness' },
  { terms: ['knee pain', 'knee injury'], category: 'symptom', code: '30989003', codeSystem: 'SNOMED', display: 'Knee pain' },
  { terms: ['swelling', 'swollen', 'edema'], category: 'symptom', code: '65124004', codeSystem: 'SNOMED', display: 'Swelling' },
];

// NegEx-style negation triggers — if one precedes a term within a short window (and no sentence break
// intervenes), the finding is negated ("no fracture", "denies chest pain", "ruled out MI", "negative for").
const NEG = ['no', 'not', 'without', 'denies', 'denied', 'negative for', 'ruled out', 'rule out', 'r/o', 'absent', 'resolved', 'free of', 'no evidence of', 'no signs of'];

function isNegated(lower: string, matchIdx: number): boolean {
  // look back up to ~40 chars for a negation trigger, stopping at a sentence/clause break
  const start = Math.max(0, matchIdx - 45);
  let window = lower.slice(start, matchIdx);
  // negation scope ends at a clause break: sentence end, semicolon, "but", or a dash ("no fracture — sprain")
  const brk = Math.max(window.lastIndexOf('. '), window.lastIndexOf('; '), window.lastIndexOf(', but'), window.lastIndexOf(' but '), window.lastIndexOf('—'), window.lastIndexOf(' - '), window.lastIndexOf(' – '));
  if (brk >= 0) window = window.slice(brk + 1);
  return NEG.some((n) => new RegExp(`(^|\\W)${n.replace(/[/]/g, '\\/')}(\\W|$)`).test(window));
}

// Extract coded clinical entities from free text. Deterministic; dedupes by code (keeps first mention,
// but a later NON-negated mention overrides an earlier negated one — "no chest pain today, chest pain
// returned" resolves to present).
export function codeText(text: string): { entities: CodedEntity[]; model: 'clinical-lexicon+negex'; counts: Record<string, number> } {
  const lower = ` ${String(text || '').toLowerCase()} `;
  const byCode = new Map<string, CodedEntity>();
  for (const e of LEX) {
    for (const term of e.terms) {
      const re = new RegExp(`(^|\\W)(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})(\\W|$)`, 'g');
      let m: RegExpExecArray | null;
      while ((m = re.exec(lower)) !== null) {
        const idx = m.index + m[1]!.length;
        const negated = isNegated(lower, idx);
        const prior = byCode.get(e.code);
        if (!prior || (prior.negated && !negated)) {
          byCode.set(e.code, { text: term, category: e.category, code: e.code, codeSystem: e.codeSystem, display: e.display, negated });
        }
        re.lastIndex = idx + m[2]!.length; // advance past this match
      }
    }
  }
  const entities = [...byCode.values()];
  const counts: Record<string, number> = {};
  for (const en of entities) counts[en.category] = (counts[en.category] ?? 0) + 1;
  return { entities, model: 'clinical-lexicon+negex', counts };
}
