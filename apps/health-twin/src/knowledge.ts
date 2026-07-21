// Medical knowledge grounding — the "ground our answers in real medical texts" attack. A clinical
// question gets a plain-language explanation CITED to an authoritative source, tagged with an evidence
// tier. This is a starter CC/guideline-sourced knowledge base for the cardiometabolic wedge; the SAME
// interface (`ground(question)`) is what the estate's BRAIN (board-exam corpus / medical texts) plugs
// into behind — see groundFromBrain(). Non-diagnostic: it explains, it does not diagnose or prescribe.

export type EvidenceTier = 'clinical-guideline' | 'systematic-review' | 'textbook-reference' | 'consensus';

interface Topic { id: string; terms: string[]; explains: string; source: string; tier: EvidenceTier }

// Curated, sourced facts. Each `explains` is plain-language; each carries its authoritative `source`.
const KB: Topic[] = [
  { id: 'prediabetes', terms: ['prediabetes', 'pre-diabetes', 'a1c', 'impaired glucose', 'blood sugar'], tier: 'clinical-guideline', source: 'ADA Standards of Care in Diabetes',
    explains: 'Prediabetes means blood sugar is higher than normal but not yet diabetes — an A1c of 5.7–6.4%. It is a warning sign, not a diagnosis of diabetes, and it is often reversible: intensive lifestyle change (about 7% weight loss + regular activity) cuts progression to type-2 diabetes by roughly 58%.' },
  { id: 'type2diabetes', terms: ['type 2 diabetes', 'diabetes', 't2dm', 'metformin'], tier: 'clinical-guideline', source: 'ADA Standards of Care in Diabetes',
    explains: 'Type-2 diabetes is diagnosed at A1c ≥6.5% (confirmed). Metformin is usually the first-line medication; newer agents (SGLT2 inhibitors, GLP-1 agonists) are added based on heart and kidney factors.' },
  { id: 'hypertension', terms: ['hypertension', 'high blood pressure', 'blood pressure', 'bp', 'systolic'], tier: 'clinical-guideline', source: 'ACC/AHA 2017 High Blood Pressure Guideline',
    explains: 'Blood pressure is staged: normal <120/80, elevated 120–129 systolic, stage-1 130–139 (or 80–89 diastolic), stage-2 ≥140/90. A single reading does not diagnose it — it takes repeated, confirmed out-of-office readings.' },
  { id: 'ldl', terms: ['ldl', 'cholesterol', 'bad cholesterol', 'lipids', 'hyperlipidemia'], tier: 'clinical-guideline', source: 'ACC/AHA 2018 Blood Cholesterol Guideline',
    explains: 'LDL ("bad") cholesterol drives plaque in arteries; a common target is under 100 mg/dL, and lower for higher-risk people. Whether to treat depends on your overall 10-year cardiovascular risk (an ASCVD estimate), not the number alone.' },
  { id: 'statins', terms: ['statin', 'atorvastatin', 'rosuvastatin', 'simvastatin', 'lipitor'], tier: 'systematic-review', source: 'Cholesterol Treatment Trialists’ meta-analyses',
    explains: 'Statins lower LDL and, across large trials, reduce heart attacks and strokes roughly proportional to the LDL drop. Benefit is clearest in four groups: known cardiovascular disease, LDL ≥190, diabetes aged 40–75, or elevated 10-year risk.' },
  { id: 'ascvd', terms: ['ascvd', 'cardiovascular risk', 'heart risk', '10-year risk'], tier: 'clinical-guideline', source: 'ACC/AHA Pooled Cohort Equations',
    explains: 'The 10-year ASCVD risk estimate combines age, sex, blood pressure, cholesterol, diabetes, and smoking to gauge heart-attack/stroke risk — it is how clinicians decide whether cholesterol or blood-pressure treatment is worth it for you.' },
  { id: 'egfr', terms: ['egfr', 'gfr', 'kidney', 'creatinine', 'ckd', 'renal'], tier: 'clinical-guideline', source: 'KDIGO Chronic Kidney Disease Guideline',
    explains: 'eGFR estimates how well the kidneys filter. Below 60 for at least 3 months (or albumin in the urine) meets the threshold for chronic kidney disease. Mild reductions are common and are usually monitored, especially alongside blood pressure and diabetes.' },
  { id: 'a1c-test', terms: ['hemoglobin a1c', 'hba1c', 'glycated'], tier: 'textbook-reference', source: 'MedlinePlus / clinical reference',
    explains: 'HbA1c reflects average blood sugar over the past ~3 months. It is not affected by a single meal, which is why it is used to screen for and monitor diabetes.' },
  { id: 'knee-sprain', terms: ['sprain', 'knee', 'knee injury', 'ligament'], tier: 'textbook-reference', source: 'StatPearls (knee sprain)',
    explains: 'A sprain is a stretched or torn ligament. A normal X-ray rules out fracture but not soft-tissue injury. Most simple sprains heal with rest, ice, compression, and elevation (RICE) over a few weeks.' },
  { id: 'lifestyle', terms: ['lifestyle', 'diet', 'exercise', 'weight loss', 'prevention'], tier: 'systematic-review', source: 'Diabetes Prevention Program (DPP)',
    explains: 'For prediabetes and cardiovascular risk, structured lifestyle change — modest weight loss plus ~150 minutes of activity weekly — outperformed medication for preventing diabetes in the landmark DPP trial.' },
];

export interface Grounded {
  question: string;
  grounded: boolean;
  answer: string;
  citations: { topic: string; source: string; tier: EvidenceTier }[];
  retrieval: 'local-kb' | 'brain';
}

const words = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').split(/\s+/).filter(Boolean);

// Ground a clinical question in the knowledge base: retrieve the best-matching sourced topics and
// compose a cited explanation. Deterministic; every sentence traces to a named source.
export function ground(question: string): Grounded {
  const q = String(question || '').trim();
  const ws = new Set(words(q));
  const scored = KB.map((t) => ({ t, score: t.terms.reduce((n, term) => n + (term.split(' ').every((w) => ws.has(w)) ? 1 : 0), 0) }))
    .filter((x) => x.score > 0).sort((a, b) => b.score - a.score);
  const hits = scored.slice(0, 2).map((x) => x.t);
  if (hits.length === 0) return { question: q, grounded: false, answer: '', citations: [], retrieval: 'local-kb' };
  return {
    question: q, grounded: true,
    answer: hits.map((t) => t.explains).join(' '),
    citations: hits.map((t) => ({ topic: t.id, source: t.source, tier: t.tier })),
    retrieval: 'local-kb',
  };
}

// The estate's BRAIN: the Noetica agent-machine serves 125k USMLE-textbook chunks (MedRAG) behind
// POST /api/study/retrieve {query, fields:["medicine"], topK}. When NOETICA_AM_URL is set (and the
// medicine field is vectorized + the server is up), this grounds answers in that real corpus with
// citations; otherwise it returns null and the caller falls back to the local sourced KB. Same Grounded
// shape either way, so nothing downstream changes. (Reuse-first: we ground in the brain we already test.)
interface StudyHit { text: string; slug?: string; source?: string; material?: string; score?: number }
export async function groundFromBrain(question: string): Promise<Grounded | null> {
  const url = process.env.NOETICA_AM_URL;
  if (!url) return null;
  const ac = new AbortController(); const t = setTimeout(() => ac.abort(), 5000);
  try {
    const r = await fetch(`${url}/api/study/retrieve`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ query: question, fields: ['medicine'], topK: 6 }), signal: ac.signal });
    if (!r.ok) return null;
    const d = (await r.json()) as { hits?: StudyHit[] };
    const hits = (d.hits ?? []).slice(0, 3);
    if (hits.length === 0) return null;
    return {
      question, grounded: true,
      answer: hits.map((h) => h.text.trim()).join(' '),
      citations: hits.map((h) => ({ topic: h.slug ?? 'passage', source: h.source ?? h.material ?? 'USMLE textbook corpus (MedRAG)', tier: 'textbook-reference' as EvidenceTier })),
      retrieval: 'brain',
    };
  } catch { return null; }
  finally { clearTimeout(t); }
}
