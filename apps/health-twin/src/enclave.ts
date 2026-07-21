// First slice of the doctor community over confidential compute. Runs the blinded-consult aggregation
// INSIDE an attested enclave over a SCOPED COMMUNITY POOL: de-identified case results from many providers
// are pooled by scope (region / specialty / evidence tier / practice type), aggregated into a community
// concordance signal, and returned with an ATTESTATION (which code ran, over which inputs, producing
// which output — as digests, never the raw data) + a receipt.
//
// HONEST: this is a walking skeleton. The attestation here is a hash-based stand-in for a real TEE quote
// (AWS Nitro Enclave / Intel TDX-SGX / AMD SEV-SNP measurement). The pool is synthetic. What's REAL is
// the CONTRACT — the enclave sees de-identified inputs only and emits digests + a result, never raw data
// — and the shape a real enclave will fill. Non-diagnostic: it aggregates blinded opinions; a clinician
// decides.

function djb2(s: string): string { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff; return (h >>> 0).toString(16).padStart(8, '0'); }

export interface Scope { region?: string; specialty?: string; evidenceTier?: string; practiceType?: string }

// A de-identified case result a provider's blinded panel contributed to the community pool. NO patient
// data — only the panel's outcome. This is what crosses into the enclave.
interface PoolCase { caseId: string; scope: Required<Scope>; verdict: 'unanimous' | 'majority' | 'split'; topRead: string; n: number }

// synthetic community pool (stands in for federated, consented, de-identified panels across providers)
const POOL: PoolCase[] = [
  { caseId: 'c1', scope: { region: 'US', specialty: 'cardiology', evidenceTier: 'real-world', practiceType: 'academic' }, verdict: 'majority', topRead: 'Early hypertension — monitor + lifestyle', n: 3 },
  { caseId: 'c2', scope: { region: 'US', specialty: 'cardiology', evidenceTier: 'real-world', practiceType: 'community' }, verdict: 'unanimous', topRead: 'Early hypertension — monitor + lifestyle', n: 4 },
  { caseId: 'c3', scope: { region: 'EU', specialty: 'cardiology', evidenceTier: 'guideline', practiceType: 'academic' }, verdict: 'majority', topRead: 'Early hypertension — monitor + lifestyle', n: 5 },
  { caseId: 'c4', scope: { region: 'EU', specialty: 'cardiology', evidenceTier: 'guideline', practiceType: 'community' }, verdict: 'split', topRead: 'More tests before labeling', n: 4 },
  { caseId: 'c5', scope: { region: 'US', specialty: 'internal-medicine', evidenceTier: 'real-world', practiceType: 'community' }, verdict: 'majority', topRead: 'Confirm readings; recheck lipids', n: 3 },
  { caseId: 'c6', scope: { region: 'AU', specialty: 'cardiology', evidenceTier: 'guideline', practiceType: 'community' }, verdict: 'unanimous', topRead: 'Early hypertension — monitor + lifestyle', n: 3 },
  { caseId: 'c7', scope: { region: 'US', specialty: 'cardiology', evidenceTier: 'trial', practiceType: 'academic' }, verdict: 'majority', topRead: 'Statin discussion given LDL + risk', n: 6 },
  { caseId: 'c8', scope: { region: 'EU', specialty: 'internal-medicine', evidenceTier: 'guideline', practiceType: 'academic' }, verdict: 'split', topRead: 'Secondary workup first', n: 4 },
];

export interface Attestation {
  enclave: 'skeleton-tee';
  measurement: string;   // hash of the code identity/version — a real TEE's PCR/MRENCLAVE analogue
  inputsDigest: string;  // hash of the de-identified pooled inputs — proves what was computed on, not the data
  outputDigest: string;  // hash of the result
  scope: Scope;
  note: string;
  at: string;
}

const CODE_ID = 'blinded-community-aggregate@v1'; // what a real enclave would measure

const matches = (c: PoolCase, s: Scope) =>
  (!s.region || c.scope.region === s.region) && (!s.specialty || c.scope.specialty === s.specialty) &&
  (!s.evidenceTier || c.scope.evidenceTier === s.evidenceTier) && (!s.practiceType || c.scope.practiceType === s.practiceType);

// The attested computation. In a real enclave this body runs inside the TEE; here it runs in-process but
// honours the contract: it reads only de-identified pool cases and returns a signal + digests.
export function communityAggregate(scope: Scope) {
  const cases = POOL.filter((c) => matches(c, scope));
  const n = cases.length;
  const inputsDigest = `sha-${djb2(JSON.stringify(cases.map((c) => c.caseId).sort()))}`;

  // pool the blinded verdicts + reads into a community signal — no single case is identifiable
  const verdicts = { unanimous: 0, majority: 0, split: 0 } as Record<PoolCase['verdict'], number>;
  const reads = new Map<string, number>();
  for (const c of cases) { verdicts[c.verdict]++; reads.set(c.topRead, (reads.get(c.topRead) ?? 0) + 1); }
  const concordant = verdicts.unanimous + verdicts.majority;
  const commonReads = [...reads.entries()].sort((a, b) => b[1] - a[1]).map(([read, count]) => ({ read, count }));

  const signal = {
    scope, cases: n, opinions: cases.reduce((t, c) => t + c.n, 0),
    concordanceRate: n ? Math.round((concordant / n) * 100) / 100 : 0,
    verdicts, commonReads,
    reading: n === 0 ? 'no cases in this scope yet'
      : concordant / n >= 0.7 ? `across ${n} blinded panels in this scope, most reached a concordant read — commonly: "${commonReads[0]?.read}"`
      : `across ${n} blinded panels in this scope, reads are mixed — a case worth more independent review`,
  };

  const outputDigest = `sha-${djb2(JSON.stringify({ verdicts, commonReads, n }))}`;
  const attestation: Attestation = {
    enclave: 'skeleton-tee', measurement: `sha-${djb2(CODE_ID)}`, inputsDigest, outputDigest, scope,
    note: 'Skeleton attestation (hash stand-in for a real TEE quote). The enclave sees de-identified pooled inputs only and emits digests + the result — never the raw data. Real deployment: AWS Nitro Enclave / Intel TDX-SGX / AMD SEV-SNP.',
    at: new Date().toISOString(),
  };
  return {
    signal, attestation,
    receipt: { id: `ht-community-${djb2([inputsDigest, outputDigest].join('|'))}`, verifier: 'health-twin-enclave', at: new Date().toISOString() },
    disclaimer: 'A community concordance signal from blinded, de-identified panels — computed under attestation, not a diagnosis. A clinician decides.',
  };
}

// what scopes the pool actually spans (for the UI to offer real filters)
export function communityScopes() {
  const dims: Record<string, Set<string>> = { region: new Set(), specialty: new Set(), evidenceTier: new Set(), practiceType: new Set() };
  for (const c of POOL) for (const k of Object.keys(dims)) dims[k]!.add((c.scope as any)[k]);
  return { poolSize: POOL.length, region: [...dims.region!], specialty: [...dims.specialty!], evidenceTier: [...dims.evidenceTier!], practiceType: [...dims.practiceType!] };
}
