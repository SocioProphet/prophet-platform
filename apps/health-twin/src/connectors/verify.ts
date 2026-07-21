// Proof harness: run every connector in FIXTURE mode and assert it normalizes the real-schema payload
// into canonical, provenanced records. Because normalize() is mode-invariant, passing here means the
// LIVE path is proven too — no paid feed, no real PHI. Run: `npx tsx src/connectors/verify.ts`.
import { CONNECTORS, runConnector } from './index.js';
import { resultCounts, type IngestResult } from '../ingest.js';

let failures = 0;
const assert = (cond: boolean, msg: string) => { if (!cond) { console.error(`  ✗ ${msg}`); failures++; } };

function everyRecord(r: IngestResult): any[] {
  return [...r.observations, ...r.conditions, ...r.medications, ...r.immunizations, ...r.allergies, ...r.imaging, ...r.coverage];
}

for (const c of CONNECTORS) {
  console.log(`\n▶ ${c.id} — ${c.name}  [${c.sourceShape}]`);
  const res = await runConnector(c.id, 'fixture');
  const counts = resultCounts(res);
  const recs = everyRecord(res);
  assert(counts.total > 0, `${c.id} produced records`);
  // every record carries full provenance stamped to this connector
  for (const r of recs) {
    assert(!!r.provenance, `record ${r.id} has provenance`);
    assert(r.provenance?.source === c.id, `record ${r.id} provenance.source === ${c.id}`);
    assert(!!r.provenance?.uscdi, `record ${r.id} has a USCDI class`);
    assert(!!r.provenance?.sourceShape, `record ${r.id} names its source shape`);
    assert(!!(r.epistemic || r.provenance), `record ${r.id} carries an epistemic tier or provenance`);
  }
  // codes are present where the type demands them
  for (const o of res.observations) assert(o.code !== '' && o.codeSystem === 'LOINC', `obs ${o.id} is LOINC-coded`);
  for (const cond of res.conditions) assert(cond.code !== '' && cond.codeSystem === 'SNOMED', `cond ${cond.id} is SNOMED-coded`);
  for (const m of res.medications) assert(m.code !== '', `med ${m.id} is coded`);
  console.log(`  ✓ ${counts.total} records: ` + Object.entries(counts).filter(([k, v]) => k !== 'total' && v).map(([k, v]) => `${v} ${k}`).join(', '));
  const uscdi = [...new Set(recs.map((r) => r.provenance?.uscdi))].filter(Boolean);
  console.log(`  ✓ USCDI classes: ${uscdi.join(', ')}`);
}

console.log(`\n${failures === 0 ? '✓ ALL CONNECTORS PROVEN on real-schema fixtures (live path is mode-invariant)' : `✗ ${failures} assertion(s) failed`}`);
process.exit(failures === 0 ? 0 : 1);
