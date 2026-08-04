// population.ts — the population & operations layer (surface 5). It is the privacy-preserving INVERSE
// of the contact-tracing early-warning architecture: instead of tracking individuals' spatiotemporal
// trajectories, it reads a DE-IDENTIFIED aggregate pool and surfaces high-risk cohorts, rising acuity,
// and care gaps (e.g. an LDL-over-target patient not on a statin). Two hard privacy rules: a
// k-ANONYMITY floor (a cohort with n < K is never reported — suppressed) and AGGREGATES ONLY (counts
// and rates leave, never an individual record). Receipted. Non-diagnostic — an operations view for
// care teams and payers, not a diagnosis and not surveillance.
import { mintId } from './ids.js';

export type Acuity = 'stable' | 'watch' | 'worsening' | 'critical';
interface CohortMember { ageBand: string; sex: string; conditions: string[]; acuity: Acuity; onStatin: boolean; ldlOverTarget: boolean }

const K = Math.max(2, Number(process.env.HEALTH_TWIN_POP_K ?? 11)); // k-anonymity floor (HIPAA-ish default)

// Synthetic DE-IDENTIFIED cohort (demo). In production this is an attested-enclave aggregate — no raw
// records, no identifiers, no location. Deterministic so the numbers are stable across boots.
function synthCohort(n = 80): CohortMember[] {
  const bands = ['40s', '50s', '60s', '70s'];
  const out: CohortMember[] = [];
  for (let i = 0; i < n; i++) {
    const ageBand = bands[i % bands.length]!;
    const sex = i % 2 ? 'female' : 'male';
    const htn = i % 2 === 0, dm = i % 3 === 0, hld = i % 2 === 1;
    const conditions = [htn && 'hypertension', dm && 'diabetes', hld && 'hyperlipidemia'].filter(Boolean) as string[];
    const ldlOverTarget = hld && i % 4 !== 0;
    const onStatin = hld && i % 5 === 0;          // most hyperlipidemia members are NOT on a statin → a care gap
    const load = conditions.length + (ldlOverTarget ? 1 : 0);
    const acuity: Acuity = load >= 3 ? 'critical' : load === 2 ? 'worsening' : load === 1 ? 'watch' : 'stable';
    out.push({ ageBand, sex, conditions, acuity, onStatin, ldlOverTarget });
  }
  return out;
}

const ACUITY_BAD = new Set<Acuity>(['worsening', 'critical']);

export interface CohortRisk {
  key: string; n: number;
  risingAcuityRate: number;     // share worsening/critical (the early-warning signal)
  statinCareGapRate: number;    // share LDL-over-target NOT on a statin (a closable care gap)
  riskBand: 'low' | 'elevated' | 'high';
}
export interface PopulationReport {
  asOf: string;
  kAnonymity: number;
  cohorts: CohortRisk[];
  suppressedCohorts: number;    // cohorts hidden because n < K (privacy floor)
  poolSize: number;
  earlyWarnings: string[];      // cohorts crossing the rising-acuity threshold
  receipt: string;
  disclaimer: string;
}

const round = (n: number) => Math.round(n * 100) / 100;

export function populationRisk(cohort: CohortMember[] = synthCohort()): PopulationReport {
  // group by age band × primary condition — a coarse, non-identifying cohort key
  const groups = new Map<string, CohortMember[]>();
  for (const m of cohort) {
    const key = `${m.ageBand} · ${m.conditions[0] ?? 'no-chronic-condition'}`;
    groups.set(key, [...(groups.get(key) ?? []), m]);
  }

  const cohorts: CohortRisk[] = [];
  let suppressed = 0;
  for (const [key, members] of groups) {
    if (members.length < K) { suppressed++; continue; } // k-anonymity: never report a small cell
    const rising = members.filter((m) => ACUITY_BAD.has(m.acuity)).length / members.length;
    const gapDenom = members.filter((m) => m.ldlOverTarget).length;
    const gap = gapDenom ? members.filter((m) => m.ldlOverTarget && !m.onStatin).length / gapDenom : 0;
    cohorts.push({
      key, n: members.length,
      risingAcuityRate: round(rising), statinCareGapRate: round(gap),
      riskBand: rising >= 0.5 ? 'high' : rising >= 0.25 ? 'elevated' : 'low',
    });
  }
  cohorts.sort((a, b) => b.risingAcuityRate - a.risingAcuityRate);

  const earlyWarnings = cohorts.filter((c) => c.riskBand === 'high').map((c) => `${c.key}: ${Math.round(c.risingAcuityRate * 100)}% rising acuity (n=${c.n})`);

  return {
    asOf: new Date().toISOString(),
    kAnonymity: K,
    cohorts,
    suppressedCohorts: suppressed,
    poolSize: cohort.length,
    earlyWarnings,
    receipt: mintId('receipt'),
    disclaimer: 'Population operations view over DE-IDENTIFIED aggregates only — counts and rates, never an individual record, and cohorts below the k-anonymity floor are suppressed. Non-diagnostic; not surveillance.',
  };
}
