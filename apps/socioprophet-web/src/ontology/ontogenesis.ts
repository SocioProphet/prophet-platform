// Ontogenesis upper-ontology governance for GAIA WorldClaims.
// Ontogenesis (~/dev/ontogenesis_repo, "Human Digital Twin Ontology" v0.3.0) defines
// a canonical "Ω Ladder" — a SKOS concept scheme grading how far a datum has climbed
// the path to truth — enforced by SHACL (hasOmegaState sh:in the seven states,
// minCount 1; stepsToTruth xsd:integer minInclusive 0). We adopt that ladder to
// classify every WorldClaim, so the map's data isn't just structured (GAIA) but
// GOVERNED ON AN OPEN ONTOLOGY (ontogenesis) — the depth Palantir's closed ontology
// can't expose. Sourced verbatim from ontogenesis_repo/skos/omega.ttl.
//
// NB: we deliberately do NOT synthesize ontogenesis' MembershipVector (mCBD/mCGT/mNHY)
// here — that targets human-digital-twin / FHIRResource nodes, not geospatial claims.
// Applying it to a WorldClaim would mis-use the ontology.
import type { WorldClaim } from '../gaia/worldClaim';

export const OMEGA_LADDER = [
  { id: 'ABSENT', notation: 0 },
  { id: 'SEEDED', notation: 1 },
  { id: 'NORMALIZED', notation: 2 },
  { id: 'LINKED', notation: 3 },
  { id: 'TRUSTED', notation: 4 },
  { id: 'ACTIONABLE', notation: 5 },
  { id: 'DELIVERED', notation: 6 },
] as const;
export type OmegaState = typeof OMEGA_LADDER[number]['id'];

const ACTIONABLE_NOTATION = 5;
export const notationOf = (o: OmegaState): number => OMEGA_LADDER.find((x) => x.id === o)?.notation ?? -1;
const hasRealEvidence = (c: WorldClaim) => c.source_evidence.some((e) => e.source_type !== 'synthetic_fixture');

// Grade a WorldClaim onto the Ω ladder from its GAIA policy status, evidence and
// uncertainty. The two vocabularies compose: GAIA governs admissibility, ontogenesis
// grades maturity toward actionable truth.
export function omegaForClaim(c: WorldClaim): OmegaState {
  if (c.policy_status.status === 'rejected') return 'ABSENT';
  if (!hasRealEvidence(c)) return 'SEEDED'; // present, but synthetic — not yet normalized against reality
  if (c.policy_status.status === 'proposed') return 'NORMALIZED';
  if (c.policy_status.status === 'provisional' || c.policy_status.status === 'review') return 'LINKED';
  // admitted + real evidence:
  return c.uncertainty.confidence_score >= 0.85 ? 'ACTIONABLE' : 'TRUSTED';
}

// Rungs remaining until a claim is ACTIONABLE (the ontogenesis stepsToTruth analogue).
export const stepsToActionable = (o: OmegaState): number => Math.max(0, ACTIONABLE_NOTATION - notationOf(o));

export interface OmegaConformance {
  omega: OmegaState;
  notation: number;
  stepsToActionable: number;
  conformant: boolean;
  violations: string[];
}

// SHACL-flavoured conformance check, in TS. Validates the assigned Ω state against
// the canonical scheme AND the cross-ontology invariants that tie GAIA policy status
// to ladder position — so a future change that badges synthetic data as ACTIONABLE,
// or an admitted claim as SEEDED, trips a violation instead of silently lying.
export function omegaConformance(c: WorldClaim, omega: OmegaState = omegaForClaim(c)): OmegaConformance {
  const violations: string[] = [];
  const n = notationOf(omega);
  if (n < 0) violations.push(`Ω state "${omega}" is not in the canonical Ω scheme`);
  if (c.policy_status.status === 'admitted' && n < notationOf('TRUSTED')) violations.push('admitted GAIA claim graded below TRUSTED on the Ω ladder');
  if (!hasRealEvidence(c) && n > notationOf('SEEDED')) violations.push('synthetic-only evidence graded above SEEDED');
  if (c.policy_status.status === 'rejected' && n !== 0) violations.push('rejected claim must be ABSENT (Ω 0)');
  return { omega, notation: n, stepsToActionable: stepsToActionable(omega), conformant: violations.length === 0, violations };
}
