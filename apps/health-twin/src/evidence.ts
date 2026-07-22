// Evidence grounded ON the twin — contextually and evidentiarily. For each notable finding on the
// person's record (an out-of-range lab, an active condition), we build a CONTEXTUAL query — the finding
// plus the patient's own context (age, sex, comorbidities) — retrieve grounding from the medical brain
// (Noetica /api/study/retrieve, 125k USMLE chunks) or the local sourced KB, and attach it EVIDENTIARILY
// to the specific record it backs. So the twin's findings become evidence-backed and patient-specific,
// not generic. Non-diagnostic: it cites what the literature says about the person's own numbers.
import { OBSERVATIONS, CONDITIONS, SUBJECT } from './data.js';
import { ground, groundFromBrain, type EvidenceTier } from './knowledge.js';

export interface TwinEvidence {
  recordId: string;      // the twin record this evidence backs (evidentiary link)
  finding: string;       // the person's own finding
  query: string;         // the CONTEXTUAL query sent to the brain (finding + patient context)
  evidence: string;      // what the literature says
  citations: { source: string; tier: EvidenceTier }[];
  retrieval: 'brain' | 'local-kb';
}

const outOfRange = (o: { value: number; refHigh?: number; refLow?: number }) =>
  (o.refHigh != null && o.value > o.refHigh) || (o.refLow != null && o.value < o.refLow);

export async function groundTwin(): Promise<{ context: string; items: TwinEvidence[]; disclaimer: string }> {
  const s = SUBJECT as any;
  const comorbid = CONDITIONS.map((c) => c.display.toLowerCase()).join(', ');
  // the patient context that makes retrieval SPECIFIC to this person
  const context = `${s.ageBand ?? ''} ${s.sex ?? ''}${comorbid ? `, history of ${comorbid}` : ''}`.trim();

  const findings: { recordId: string; finding: string; term: string }[] = [
    ...OBSERVATIONS.filter(outOfRange).map((o) => ({ recordId: o.id, finding: `${o.display} ${o.value} ${o.unit} (ref ${o.refLow ?? '–'}–${o.refHigh ?? '–'})`, term: o.display })),
    ...CONDITIONS.map((c) => ({ recordId: c.id, finding: c.display, term: c.display })),
  ];

  const items: TwinEvidence[] = [];
  for (const f of findings) {
    // CONTEXTUAL + CLINICALLY FRAMED: leading with "evaluation and management of <finding>" pulls the
    // on-topic clinical passage; a bare "<term> <demographics>" query drifts into demographic noise
    // (measured: reproductive-biology exam vs. the pharmacology passage we want). Comorbidities stay
    // in the query — they're the clinically-relevant context; age/sex stay in the displayed context.
    const query = `clinical evaluation and management of ${f.term}${comorbid ? ` in a patient with ${comorbid}` : ''}`;
    const g = (await groundFromBrain(query)) ?? ground(f.term); // brain (contextual) → else local KB
    if (!g.grounded) continue;
    items.push({
      recordId: f.recordId, finding: f.finding, query,     // EVIDENTIARY: bound to the record
      evidence: g.answer, citations: g.citations.map((c) => ({ source: c.source, tier: c.tier })), retrieval: g.retrieval,
    });
  }
  return {
    context, items,
    disclaimer: 'Evidence from the medical literature about the patient\'s OWN findings, contextualized to their record and cited — informational, not a diagnosis. A clinician decides.',
  };
}
