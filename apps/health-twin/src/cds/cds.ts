// Wall 3 — clinician workflow. The twin is a CDS Hooks service: an EHR fires a hook at the decision
// moment (patient-view, order-select) and we return Cards carrying the twin's consolidated record —
// every fact CITED to its source, tagged with its epistemic TIER, any inferential claim VERIFIED via
// holmes, and the whole thing framed NON-DIAGNOSTICALLY. This is the anti-Watson design pushed into the
// clinician's screen: no assertion sold as truth without provenance. Cards also carry a SMART launch
// link to open the full twin in context. Standards: HL7 CDS Hooks 2.0.
import { SUBJECT, OBSERVATIONS, CONDITIONS, type Observation, type EpistemicMode } from '../data.js';
import { dedupeIngested } from '../reconcile/reconcile.js';
import { verifyClaims } from '../reconcile/clients.js';
import type { IngestResult } from '../ingest.js';

const NONDX = 'Informational only — organizes the patient\'s own records across sources. Not a diagnosis, not a treatment recommendation. A clinician decides.';
const SOURCE = { label: 'Digital Health Twin (sovereign PHR, non-diagnostic)' };

// CDS Hooks discovery — GET /cds-services
export function discovery() {
  return {
    services: [
      { hook: 'patient-view', id: 'health-twin-patient-summary', title: 'Health Twin — consolidated record',
        description: 'Cross-source, cited, epistemic-tiered summary of the patient\'s own records (non-diagnostic).' },
      { hook: 'order-select', id: 'health-twin-medication-reconciliation', title: 'Health Twin — medication reconciliation',
        description: 'Reconciled medication list across the patient\'s connected sources, with source provenance (non-diagnostic).' },
    ],
  };
}

const tierLabel: Record<EpistemicMode, string> = { attested: 'clinician-attested', verified: 'lab-verified', derived: 'derived', observed: 'device-measured', hypothesis: 'unconfirmed' };
const arrow = (t?: number[]) => (t && t.length > 1 ? (t[t.length - 1]! > t[0]! ? '↑ rising' : t[t.length - 1]! < t[0]! ? '↓ falling' : '→ stable') : '');
const outOfRange = (o: Observation) => (o.refHigh != null && o.value > o.refHigh) || (o.refLow != null && o.value < o.refLow);

// factual, data-grounded statements (never inference beyond what the record says) → later verified
function statedFacts(): { text: string; tier: EpistemicMode; source: string }[] {
  const facts: { text: string; tier: EpistemicMode; source: string }[] = [];
  for (const o of OBSERVATIONS) {
    if (outOfRange(o)) facts.push({ text: `${o.display} is ${o.value} ${o.unit}, outside the reference range (${o.refLow ?? '–'}–${o.refHigh ?? '–'})${arrow(o.trend) ? `, ${arrow(o.trend)}` : ''}.`, tier: o.epistemic, source: 'lab' });
  }
  for (const c of CONDITIONS) facts.push({ text: `${c.display} is on the problem list (${c.clinicalStatus}).`, tier: c.epistemic, source: 'problem-list' });
  return facts;
}

// Route every stated fact through holmes for grounding — label the verdict, never assert raw. If holmes
// is down we mark facts 'unverified (grounding offline)' rather than presenting them as established.
async function verify(facts: { text: string }[]): Promise<{ verified: number; total: number; verdicts: Record<string, string>; online: boolean }> {
  if (facts.length === 0) return { verified: 0, total: 0, verdicts: {}, online: true };
  const v = await verifyClaims(facts.map((f) => f.text));
  if (!v.ok) return { verified: 0, total: facts.length, verdicts: {}, online: false };
  const verdicts: Record<string, string> = {};
  let verified = 0;
  for (const r of v.data.results) { verdicts[r.claim] = r.verdict; if (r.verdict === 'supported' || r.verdict === 'weakly-supported') verified++; }
  return { verified, total: facts.length, verdicts, online: true };
}

function smartLink(baseUrl: string) {
  return { label: 'Open Health Twin in context', url: `${baseUrl.replace(/\/$/, '')}/health`, type: 'smart' as const };
}

// patient-view → the consolidated-record card
export async function patientSummaryCards(ingested: IngestResult, baseUrl: string) {
  const dedupe = await dedupeIngested(ingested);
  const facts = statedFacts();
  const checked = await verify(facts);
  const flagged = facts.filter((f) => f.source === 'lab').length;

  const factLines = facts.map((f) => {
    const v = checked.verdicts[f.text];
    const badge = !checked.online ? '_unverified (grounding offline)_' : v ? `_${v}_` : '';
    return `- ${f.text} · **${tierLabel[f.tier]}** ${badge}`;
  }).join('\n');

  const sourcesLine = dedupe.service === 'entity-resolution'
    ? `**${dedupe.after} records** reconciled from **${new Set(dedupe.golden.flatMap((g) => g.contributingSources)).size} sources** (${dedupe.merged} cross-source duplicate(s) merged).`
    : `Records held locally${dedupe.reason ? ` (reconciliation service ${dedupe.reason})` : ''}.`;

  const detail = [
    `${sourcesLine}`,
    '',
    `**On record** (cited · trust tier · grounding verdict):`,
    factLines || '- No out-of-range results or active problems on record.',
    '',
    `_Grounding: ${checked.online ? `${checked.verified}/${checked.total} facts grounded via holmes` : 'holmes offline — facts shown unverified'}._`,
    `_${NONDX}_`,
  ].join('\n');

  return {
    cards: [{
      uuid: `ht-summary-${SUBJECT.id}`,
      summary: `Health Twin: ${dedupe.after || OBSERVATIONS.length + CONDITIONS.length} records${flagged ? ` · ${flagged} result(s) out of range` : ''}`.slice(0, 140),
      indicator: flagged > 0 ? 'warning' : 'info',
      detail,
      source: SOURCE,
      links: [smartLink(baseUrl)],
    }],
  };
}

// order-select / medication-prescribe → reconciled medication card
export async function medReconciliationCards(ingested: IngestResult, baseUrl: string) {
  const dedupe = await dedupeIngested(ingested);
  const meds = dedupe.golden.filter((g) => g.members.some((m) => m.includes('med') || m.includes('fill')));
  const lines = meds.length
    ? meds.map((g) => `- **${g.name}**${g.contributingSources.length > 1 ? ` — confirmed by ${g.contributingSources.join(' + ')}` : ` — ${g.contributingSources[0] ?? 'one source'}`}`).join('\n')
    : '- No reconciled medications yet (connect a source).';
  const detail = [
    `**Reconciled medication list** across the patient's connected sources:`,
    lines,
    '',
    `_Cross-source confirmation is provenance, not a clinical judgment._`,
    `_${NONDX}_`,
  ].join('\n');
  return {
    cards: [{
      uuid: `ht-meds-${SUBJECT.id}`,
      summary: `Health Twin: ${meds.length} reconciled medication(s)`.slice(0, 140),
      indicator: 'info',
      detail,
      source: SOURCE,
      links: [smartLink(baseUrl)],
    }],
  };
}
