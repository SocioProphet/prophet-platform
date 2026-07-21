// Ask-my-agent — the patient's magic: conversational recall over a lifetime of records. "Where did I
// hurt my knee as a kid — and what was the outcome?" → a plain-language answer, WITH the source records
// cited and their epistemic tier. LOCAL-FIRST by design: this runs a sovereign keyword-relevance recall
// over the person's own twin (no cloud needed). When hellgraph-service is reachable it can add hybrid
// semantic grounding on top — but the twin answers on its own node first. Non-diagnostic: it recalls and
// cites the person's records; it does not diagnose.
import { SUBJECT, SYSTEMS, OBSERVATIONS, CONDITIONS, ENCOUNTERS, IMAGING, MEDICATIONS, ALLERGIES, IMMUNIZATIONS } from './data.js';
import { ground, type Grounded } from './knowledge.js';

export interface Citation { id: string; kind: 'lab' | 'condition' | 'encounter' | 'imaging' | 'medication' | 'allergy' | 'immunization'; text: string; date?: string; tier?: string; system?: string }
export interface AskAnswer { question: string; answer: string; citations: Citation[]; retrieval: 'local-recall' | 'local-recall+hellgraph'; grounded?: Grounded; nonDiagnostic: true }

// build a flat, searchable index of every record in the twin (each row keeps its provenance for citing)
interface Row { id: string; kind: Citation['kind']; text: string; hay: string; date?: string; tier?: string; system?: string }
function index(): Row[] {
  const rows: Row[] = [];
  for (const o of OBSERVATIONS) rows.push({ id: o.id, kind: 'lab', text: `${o.display}: ${o.value} ${o.unit} (${o.effective})`, hay: `${o.display} ${o.code} ${o.system} ${o.organ} lab result value`.toLowerCase(), date: o.effective, tier: o.epistemic, system: o.system });
  for (const c of CONDITIONS) rows.push({ id: c.id, kind: 'condition', text: `${c.display} — ${c.clinicalStatus}, onset ${c.onset}`, hay: `${c.display} ${c.code} ${c.system} ${c.organ} condition diagnosis problem`.toLowerCase(), date: c.onset, tier: c.epistemic, system: c.system });
  for (const e of ENCOUNTERS) rows.push({ id: e.id, kind: 'encounter', text: `${e.type} (${e.date}) — ${e.provider}: ${e.note}`, hay: `${e.type} ${e.provider} ${e.note} ${e.system} visit encounter`.toLowerCase(), date: e.date, system: e.system });
  for (const im of IMAGING) rows.push({ id: im.id, kind: 'imaging', text: `${im.modality} of ${im.bodySite} (${im.date}) — ${im.description}`, hay: `${im.modality} ${im.bodySite} ${im.description} ${im.system} imaging scan xray mri ct`.toLowerCase(), date: im.date, tier: im.epistemic, system: im.system });
  for (const m of MEDICATIONS) rows.push({ id: m.id, kind: 'medication', text: `${m.display} — ${m.dose} (${m.status}, since ${m.started})`, hay: `${m.display} ${m.code} medication drug pill prescription taking on meds ${m.system} ${m.organ}`.toLowerCase(), date: m.started, tier: m.epistemic, system: m.system });
  for (const a of ALLERGIES) rows.push({ id: a.id, kind: 'allergy', text: `Allergy: ${a.display} — ${a.reaction} (${a.criticality})`, hay: `${a.display} allergy allergic reaction ${a.reaction}`.toLowerCase(), tier: a.epistemic });
  for (const im of IMMUNIZATIONS) rows.push({ id: im.id, kind: 'immunization', text: `${im.display} vaccine (${im.date})`, hay: `${im.display} immunization vaccine vaccinated shot flu tdap`.toLowerCase(), date: im.date, tier: im.epistemic });
  return rows;
}

const STOP = new Set(['the', 'a', 'an', 'i', 'my', 'me', 'was', 'were', 'is', 'are', 'did', 'do', 'what', 'when', 'where', 'how', 'and', 'or', 'to', 'of', 'in', 'on', 'for', 'that', 'this', 'it', 'as', 'kid', 'child', 'ago', 'years', 'year', 'old', 'have', 'had', 'has', 'outcome', 'result', 'up', 'any', 'anything', 'currently', 'taking', 'about', 'been', 'am', 'get', 'got']);
const SYN: Record<string, string[]> = { knee: ['knee', 'leg', 'joint'], heart: ['heart', 'cardiac', 'cardiovascular', 'bp', 'blood', 'pressure', 'cholesterol', 'ldl'], brain: ['brain', 'head', 'nervous', 'mri'], sugar: ['sugar', 'glucose', 'a1c', 'diabetes', 'prediabetes', 'pancreas'], kidney: ['kidney', 'renal', 'egfr'], liver: ['liver', 'hepatic', 'alt'], lung: ['lung', 'chest', 'respiratory', 'x-ray', 'xray'] };

function terms(q: string): string[] {
  const base = q.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').split(/\s+/).filter((w) => w && !STOP.has(w));
  const expanded = new Set(base);
  for (const w of base) {
    if (w.endsWith('s') && w.length > 3) expanded.add(w.slice(0, -1)); // crude stem: medications→medication
    for (const [, syns] of Object.entries(SYN)) if (syns.includes(w)) syns.forEach((s) => expanded.add(s));
  }
  return [...expanded];
}

// Recall: score every record against the question's terms, take the best few, and compose a plain answer
// that CITES them. Deterministic — no model prose, so the "answer" is grounded in the records themselves.
export function ask(question: string): AskAnswer {
  const q = String(question || '').trim();
  const ts = terms(q);
  const wordRe = (t: string) => new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
  // whole-word match (not substring) — so "on" doesn't match inside "prescription", etc.
  const scored = index().map((r) => ({ r, score: ts.reduce((n, t) => n + (wordRe(t).test(r.hay) ? 1 : 0), 0) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || (a.r.date && b.r.date ? (a.r.date < b.r.date ? -1 : 1) : 0));
  const hits = scored.slice(0, 4).map((x) => x.r);
  const citations: Citation[] = hits.map((r) => ({ id: r.id, kind: r.kind, text: r.text, date: r.date, tier: r.tier, system: r.system }));

  let answer: string;
  if (!q) answer = 'Ask me anything about your records — e.g. "where did I hurt my knee?" or "are my cholesterol numbers going up?"';
  else if (hits.length === 0) answer = `I couldn't find anything in your records matching that. Your twin holds ${OBSERVATIONS.length} results, ${CONDITIONS.length} conditions, ${ENCOUNTERS.length} visits and ${IMAGING.length} images — try naming a body part, a test, or a time.`;
  else {
    const oldest = hits.reduce((a, b) => (a.date && b.date && a.date < b.date ? a : b));
    const lead = hits.length === 1 ? 'Here\'s the record that matches:' : `Here's what your records show (${hits.length} related records${oldest.date ? `, earliest ${oldest.date}` : ''}):`;
    answer = `${lead}\n` + hits.map((r) => `• ${r.text}${r.tier ? ` [${r.tier}]` : ''}`).join('\n') + `\n\nThese are your own records, cited above — not a diagnosis. Your clinician can help interpret them.`;
  }
  // ground the question in authoritative medical knowledge too (cited, evidence-tiered) — so the
  // person gets their own records AND what the medicine says. Brain corpus plugs in behind ground().
  const g = ground(q);
  return { question: q, answer, citations, retrieval: 'local-recall', grounded: g.grounded ? g : undefined, nonDiagnostic: true };
}
