// Cross-domain agentic brief — the move no single-silo peer can make.
// For one location we assemble a governed WorldClaim per domain (income, crime,
// air, safety, housing, …), each carrying its GAIA policy status + ontogenesis Ω
// grade, then compose a PROVENANCE-GRADED prompt so Noetica reasons across silos
// while knowing which facts are real (admitted / ACTIONABLE) vs illustrative
// (proposed / SEEDED). Palantir can fuse domains; only we hand the model the
// per-datum truth grade with it.
import { realWorldClaim, syntheticWorldClaim, type WorldClaim, type SourceEvidence } from './worldClaim';
import { omegaForClaim } from '../ontology/ontogenesis';

// One domain input: a metric value at the location, real or synthetic.
export interface DomainInput {
  key: string;
  label: string;
  value: number;
  format?: (v: number) => string;
  real?: { source: SourceEvidence; confidence?: number; uncertaintyClass?: 'low' | 'moderate' | 'high' };
}

export interface DomainClaim { input: DomainInput; claim: WorldClaim; omega: ReturnType<typeof omegaForClaim>; display: string }

export function crossDomainClaims(cellId: string, lon: number, lat: number, inputs: DomainInput[]): DomainClaim[] {
  return inputs.map((input) => {
    const claim = input.real
      ? realWorldClaim({ cellId, lon, lat, claimType: 'observation_passthrough', value: { [input.key]: input.value }, source: input.real.source, confidence: input.real.confidence, uncertaintyClass: input.real.uncertaintyClass, uncertaintyNotes: input.real.confidence != null ? 'Real source (see evidence).' : undefined })
      : syntheticWorldClaim({ cellId, lon, lat, claimType: 'feature_classification', value: { [input.key]: input.value }, metricLabel: input.label });
    return { input, claim, omega: omegaForClaim(claim), display: input.format ? input.format(input.value) : String(input.value) };
  });
}

// Provenance-graded prompt: real (admitted) facts first as ground truth, illustrative
// facts second and explicitly flagged, so the model weights them correctly.
export function crossDomainPrompt(areaLabel: string, claims: DomainClaim[], question: string): string {
  const real = claims.filter((c) => c.claim.policy_status.status === 'admitted');
  const illustrative = claims.filter((c) => c.claim.policy_status.status !== 'admitted');
  const fmt = (c: DomainClaim) => `${c.input.label}: ${c.display}`;
  const realLine = real.length
    ? `REAL (governed world-claims, treat as ground truth — ${real.map((c) => c.input.real!.source.attribution.source_name).filter((v, i, a) => a.indexOf(v) === i).join('; ')}): ${real.map(fmt).join('; ')}.`
    : 'REAL: none yet for this area.';
  const illLine = illustrative.length
    ? `ILLUSTRATIVE (sample data, directional only — do NOT state as fact): ${illustrative.map(fmt).join('; ')}.`
    : '';
  return `${question} Area: ${areaLabel}. ${realLine} ${illLine} Reason across ALL these domains together (safety, cost, reachability, demographics, environment), weight the real figures over the illustrative ones, name the key trade-off, and say what single fact would most change the answer.`.replace(/\s+/g, ' ').trim();
}
