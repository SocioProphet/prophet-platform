// Situations ON THE MAP — bind an area's cross-domain governed WorldClaims into ONE
// n-ary Situation hyperedge (place ⊕ many claims ⊕ events). A binary graph would
// scatter these into disconnected pairwise links and lose the fact that they are one
// joint situation at one place. This is the n-ary moat, authored straight from the map.
import type { Situation, SituationMember } from './situations';
import type { DomainClaim } from '../../gaia/crossDomain';

export interface NearbyContext { events?: string[]; competitors?: number }

export function situationForArea(areaLabel: string, cellId: string, claims: DomainClaim[], nearby: NearbyContext = {}): Situation {
  const members: SituationMember[] = [{ type: 'place', label: areaLabel, role: 'location', ref: '/map' }];
  for (const c of claims) {
    const real = c.claim.policy_status.status === 'admitted';
    members.push({
      type: 'claim',
      label: `${c.input.label}: ${c.display}${real ? ' · real' : ' · illustrative'}`,
      role: `Ω ${c.omega}`,
      ref: '/map',
    });
  }
  for (const ev of nearby.events ?? []) members.push({ type: 'event', label: ev, role: 'nearby event', ref: '/map' });
  if (nearby.competitors) members.push({ type: 'instrument', label: `${nearby.competitors} competitors in view`, role: 'market context', ref: '/map' });

  const real = claims.filter((c) => c.claim.policy_status.status === 'admitted').length;
  return {
    id: `sit-area-${cellId}`,
    label: `Cross-domain situation at ${areaLabel}`,
    summary: `${claims.length} governed domain-claims (${real} real, ${claims.length - real} illustrative) bound to one place as a single n-ary situation — not ${claims.length} disconnected links.`,
    members,
    provenance: {
      source: 'map cross-domain world-claims',
      method: 'GAIA WorldClaim + ontogenesis Ω grading',
      timeObserved: new Date().toISOString(),
      confidence: claims.length ? +(real / claims.length).toFixed(2) : 0,
    },
  };
}
