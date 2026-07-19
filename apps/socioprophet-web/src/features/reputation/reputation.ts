// HolographMe reputation — portable, verified reputation carried across surfaces
// (News contributors, marketplace providers, people). Modeled BFO-style: the SCORE
// is a disposition (stable standing), TRAITS are dispositions/traits, and OCCURRENTS
// are the episodes (posts, reports, attestations) that ground it. UI-only; the real
// HolographMe lattice swaps in behind reputationFor().
export type HatKind = 'verified' | 'expert' | 'moderator' | 'local' | 'source';
export interface Hat { kind: HatKind; label: string }
export type Tier = 'trusted' | 'established' | 'emerging' | 'unrated';

export interface Reputation {
  id: string;
  aliases: string[];       // handles / names / ids this reputation answers to
  displayName: string;
  did?: string;
  score: number;           // 0..100 — disposition (stable standing)
  tier: Tier;
  hats: Hat[];
  attestations: number;
  disputes: number;
  traits: string[];        // disposition / trait descriptors
  occurrents: string[];    // recent grounding episodes
}

export const REPUTATIONS: Reputation[] = [
  { id: 'r-ada', aliases: ['ada.newhope.social', 'Ada L.', '@ada.newhope.social'], displayName: 'Ada L.', did: 'did:plc:ada7h0penn3wh0pe', score: 86, tier: 'trusted', hats: [{ kind: 'verified', label: 'verified' }, { kind: 'local', label: 'local' }], attestations: 214, disputes: 3, traits: ['careful sourcing', 'local-first'], occurrents: ['Reported storm-drain flooding (3 corroborations)', 'Posted provenance-rail explainer'] },
  { id: 'r-grace', aliases: ['grace.marketsdesk.io', 'Grace', 'Grace — Markets Desk', '@grace.marketsdesk.io'], displayName: 'Grace (Markets Desk)', did: 'did:plc:gr4cem4rketsd3sk1', score: 79, tier: 'established', hats: [{ kind: 'verified', label: 'verified' }, { kind: 'expert', label: 'markets' }], attestations: 96, disputes: 5, traits: ['markets expertise'], occurrents: ['Filed 311 on pothole cluster', 'Commodities tape thread'] },
  { id: 'r-linus', aliases: ['linus.dev', 'Linus (local-first)', '@linus.dev'], displayName: 'Linus', did: 'did:plc:l1nus0urcef0rge00', score: 74, tier: 'established', hats: [{ kind: 'verified', label: 'verified' }, { kind: 'expert', label: 'infra' }], attestations: 61, disputes: 2, traits: ['infra depth'], occurrents: ['Reported community mural unveiling', 'Sovereign-forge post'] },
  { id: 'r-berners', aliases: ['berners.policywatch.org', 'B. Berners', '@berners.policywatch.org'], displayName: 'B. Berners', did: 'did:plc:b3rnersreg0w4tch2', score: 71, tier: 'established', hats: [{ kind: 'expert', label: 'policy' }], attestations: 130, disputes: 8, traits: ['regulatory focus'], occurrents: ['Disclosure-rule brief'] },
  { id: 'r-skeptic', aliases: ['skeptic.reader.bsky.social', 'the skeptic', '@skeptic.reader.bsky.social'], displayName: 'the skeptic', did: 'did:plc:sk3pt1creader0099', score: 44, tier: 'emerging', hats: [{ kind: 'local', label: 'local' }], attestations: 44, disputes: 12, traits: ['contrarian', 'unverified reports'], occurrents: ['Filed unverified night-market report', 'Benchmark-contamination counterpoint (held)'] },
  // Marketplace providers
  { id: 'r-escondida', aliases: ['Escondida Mine', 'p-escondida'], displayName: 'Escondida Mine', score: 90, tier: 'trusted', hats: [{ kind: 'verified', label: 'verified' }, { kind: 'source', label: 'source' }], attestations: 320, disputes: 4, traits: ['reliable supply', 'audited'], occurrents: ['1,204 fulfilled shipments', 'Audited 2026-Q2'] },
  { id: 'r-bike', aliases: ['Cargo Bike Collective', 'p-bike'], displayName: 'Cargo Bike Collective', score: 52, tier: 'emerging', hats: [{ kind: 'local', label: 'local' }], attestations: 38, disputes: 6, traits: ['zero-emission', 'small operator'], occurrents: ['Launched 2026', 'Dense-urban pilots'] },
];

const tierOf = (s: number): Tier => (s >= 80 ? 'trusted' : s >= 65 ? 'established' : s >= 40 ? 'emerging' : 'unrated');

export function reputationFor(key: string): Reputation | undefined {
  if (!key) return undefined;
  const k = key.toLowerCase().replace(/^@/, '');
  return REPUTATIONS.find((r) => r.aliases.some((a) => a.toLowerCase().replace(/^@/, '') === k || a.toLowerCase().includes(k)));
}
export const TIER_META: Record<Tier, { label: string; color: string }> = {
  trusted: { label: 'Trusted', color: '#4bbf73' },
  established: { label: 'Established', color: '#58a6ff' },
  emerging: { label: 'Emerging', color: '#e3b341' },
  unrated: { label: 'Unrated', color: '#8b949e' },
};
export { tierOf };
