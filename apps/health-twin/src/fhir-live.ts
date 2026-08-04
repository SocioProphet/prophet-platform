// fhir-live.ts — the LIVE interoperability proof (verbs 1/2, write side). `fhir.ts` renders the twin
// as FHIR; this actually WRITES to a real FHIR R4 server and reads it back — closing the loop with the
// real healthcare system instead of only speaking the format. Default target is the public HAPI test
// sandbox (https://hapi.fhir.org/baseR4). SAFETY: only DE-IDENTIFIED SYNTHETIC data is ever pushed —
// no subject reference to a real patient, an explicit "synthetic demo" marker, and a synthetic
// identifier. Non-diagnostic. Opt-in: nothing is pushed unless this endpoint/script is invoked.
import { OBSERVATIONS } from './data.js';
import { mintId } from './ids.js';

const DEFAULT_TARGET = process.env.HEALTH_TWIN_FHIR_TARGET ?? 'https://hapi.fhir.org/baseR4';

// A minimal, valid FHIR R4 Observation carrying NO identity — a synthetic marker instead of a subject.
function syntheticObservation(o = OBSERVATIONS[0]!) {
  const nonce = mintId('syn').slice(0, 16);
  return {
    resourceType: 'Observation',
    status: 'final',
    identifier: [{ system: 'https://socioprophet.md/twin/synthetic', value: `synthetic-demo-${nonce}` }],
    category: [{ coding: [{ system: 'http://terminology.hl7.org/CodeSystem/observation-category', code: 'laboratory' }] }],
    code: { coding: [{ system: 'http://loinc.org', code: o.code, display: o.display }], text: o.display },
    subject: { display: 'SYNTHETIC DEMO — not a real patient (SocioProphet twin)' },
    effectiveDateTime: o.effective,
    valueQuantity: { value: o.value, unit: o.unit, system: 'http://unitsofmeasure.org', code: o.unit },
    note: [{ text: 'Synthetic, de-identified demo record written by SocioProphet health-twin to prove FHIR write-back. Not a real patient.' }],
  };
}

export interface FhirWriteProof {
  ok: boolean;
  server: string;
  wrote?: { resourceType: string; id: string; code: string; value: number; unit: string };
  readBack?: { id: string; value: number } | null;
  confirmed: boolean;              // the value we wrote == the value the server returned on read
  location?: string;
  receipt: string;
  error?: string;
  disclaimer: string;
}

// Write a synthetic Observation to a real FHIR server, then READ IT BACK and confirm the value —
// a genuine closed-loop proof. Never throws: network/server failure returns ok:false with the reason.
export async function proveFhirWriteBack(target = DEFAULT_TARGET): Promise<FhirWriteProof> {
  const base = target.replace(/\/$/, '');
  const obs = syntheticObservation();
  const receipt = mintId('receipt');
  const disclaimer = 'Live FHIR write-back of DE-IDENTIFIED SYNTHETIC data only — proves interoperability, not a real patient record. Non-diagnostic.';
  try {
    const ac = new AbortController(); const t = setTimeout(() => ac.abort(), 15_000);
    const post = await fetch(`${base}/Observation`, {
      method: 'POST', headers: { 'content-type': 'application/fhir+json', accept: 'application/fhir+json' },
      body: JSON.stringify(obs), signal: ac.signal,
    });
    if (!post.ok) { clearTimeout(t); return { ok: false, server: base, confirmed: false, receipt, error: `write failed (HTTP ${post.status})`, disclaimer }; }
    const created = await post.json();
    const id = String(created.id ?? '');
    const location = post.headers.get('location') ?? `${base}/Observation/${id}`;

    // read it back
    const get = await fetch(`${base}/Observation/${id}`, { headers: { accept: 'application/fhir+json' }, signal: ac.signal });
    clearTimeout(t);
    const readBack = get.ok ? await get.json() : null;
    const readValue = readBack?.valueQuantity?.value;
    const confirmed = readValue === obs.valueQuantity.value;

    return {
      ok: true, server: base,
      wrote: { resourceType: 'Observation', id, code: obs.code.coding[0]!.code, value: obs.valueQuantity.value, unit: obs.valueQuantity.unit },
      readBack: readBack ? { id, value: readValue } : null,
      confirmed, location, receipt, disclaimer,
    };
  } catch (e) {
    return { ok: false, server: base, confirmed: false, receipt, error: (e as Error).name === 'AbortError' ? 'timeout' : (e as Error).message, disclaimer };
  }
}

// Standalone proof: `npx tsx src/fhir-live.ts [targetBaseUrl]`
if (import.meta.url === `file://${process.argv[1]}`) {
  const target = process.argv[2] ?? DEFAULT_TARGET;
  console.log(`\n▶ LIVE FHIR WRITE-BACK PROOF → ${target}`);
  const p = await proveFhirWriteBack(target);
  if (!p.ok) { console.log(`  ✗ ${p.error}`); process.exit(1); }
  console.log(`  wrote Observation/${p.wrote!.id}: ${p.wrote!.code} = ${p.wrote!.value} ${p.wrote!.unit}`);
  console.log(`  read back value: ${p.readBack?.value}`);
  console.log(`  ${p.confirmed ? '✓ CLOSED THE LOOP — wrote to a real FHIR server and read the same value back' : '✗ value mismatch on read-back'}`);
  console.log(`  ${p.location}`);
  process.exit(p.confirmed ? 0 : 1);
}
