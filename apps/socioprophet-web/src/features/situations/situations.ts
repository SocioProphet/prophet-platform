// Situations — the n-ary hypergraph moat. A "situation" is ONE hyperedge that
// binds entities of DIFFERENT kinds (a place, a rule, people, an event, a market
// instrument, a claim) into a single joint context with provenance. A binary
// graph (Palantir-style links) can only express this as N disconnected pairwise
// edges — it loses the fact that these are one situation. This is what no
// single-silo competitor can represent. UI-only; a real deployment materializes
// these as HellGraph n-ary edges (AtomId members + sealed provenance).

export type MemberType = 'place' | 'rule' | 'person' | 'event' | 'instrument' | 'claim';

export interface SituationMember {
  type: MemberType;
  label: string;
  role: string;          // how it participates ("affected", "reporter", "authority"…)
  ref?: string;          // route/deep-link into the surface that owns this entity
}

export interface Situation {
  id: string;
  label: string;
  summary: string;
  members: SituationMember[];
  provenance: { source: string; method: string; timeObserved: string; confidence: number };
}

export const MEMBER_META: Record<MemberType, { label: string; color: string; icon: string }> = {
  place: { label: 'Place', color: '#22d3ee', icon: '📍' },
  rule: { label: 'Rule', color: '#f0883e', icon: '§' },
  person: { label: 'Person', color: '#a855f7', icon: '⚉' },
  event: { label: 'Event', color: '#e3b341', icon: '◆' },
  instrument: { label: 'Instrument', color: '#4bbf73', icon: '$' },
  claim: { label: 'Claim', color: '#58a6ff', icon: '‹›' },
};

export const SITUATIONS: Situation[] = [
  {
    id: 'sit-audit-trail',
    label: 'Cross-jurisdiction audit-trail rule takes effect over Lower Manhattan',
    summary: 'A pending audit-trail guidance binds a place, the rule itself, its authority + an affected operator, the comment-deadline event, and an exposed equity — one situation, not five links.',
    members: [
      { type: 'place', label: 'Lower Manhattan', role: 'jurisdiction', ref: '/map' },
      { type: 'rule', label: 'WG-AUD-07 · Audit-Trail Guidance', role: 'instrument', ref: '/law/international-law' },
      { type: 'person', label: 'B. Berners (policy)', role: 'authority', ref: '/people/search' },
      { type: 'person', label: 'Avery Sloan (Meridian)', role: 'affected operator', ref: '/people/search' },
      { type: 'event', label: 'Comment window closes', role: 'deadline', ref: '/news/calendar' },
      { type: 'instrument', label: 'MSFT', role: 'exposed equity', ref: '/markets/equities-preferreds' },
    ],
    provenance: { source: 'docket WG-AUD-07 + entity-resolution', method: 'ontology-guided extraction', timeObserved: '2026-07-06T14:00:00-04:00', confidence: 0.82 },
  },
  {
    id: 'sit-flooding',
    label: 'Storm-drain flooding reported at Battery Park during the nor’easter',
    summary: 'A citizen report ties a place, a weather event, the reporter, a flood-risk policy, and the reified claim into one situation with corroboration.',
    members: [
      { type: 'place', label: 'Battery Park', role: 'location', ref: '/map' },
      { type: 'event', label: 'Nor’easter (weather)', role: 'trigger', ref: '/weather/forecast' },
      { type: 'person', label: 'Ada L. (local-first)', role: 'reporter', ref: '/people/social-networks' },
      { type: 'rule', label: 'Flood-risk disclosure policy', role: 'governing rule', ref: '/law/state-local-law' },
      { type: 'claim', label: '“storm-drain backup, 3 corroborations”', role: 'asserted claim', ref: '/universe' },
    ],
    provenance: { source: 'Bluesky mirror + 311 records', method: 'claim reification + corroboration', timeObserved: '2026-07-05T08:20:00-04:00', confidence: 0.74 },
  },
  {
    id: 'sit-siteselect',
    label: 'Coffee-shop opening opportunity on a high-foot-traffic corridor',
    summary: 'A site-selection opportunity binds a place, its foot-traffic event pattern, the prospective operator, the lease instrument, and the suitability claim.',
    members: [
      { type: 'place', label: 'Corridor · SoHo', role: 'candidate site', ref: '/map' },
      { type: 'event', label: 'Lunch + evening foot-traffic peak', role: 'demand pattern', ref: '/map' },
      { type: 'person', label: 'Prospective operator', role: 'actor', ref: '/people/search' },
      { type: 'instrument', label: 'Median rent $4.2k/mo', role: 'cost input', ref: '/markets/real-assets' },
      { type: 'claim', label: '“suitability 71/100, rank #4”', role: 'verified score', ref: '/map' },
    ],
    provenance: { source: 'site-selection engine (verified compute)', method: 'weighted profile + reachability', timeObserved: '2026-07-07T11:00:00-04:00', confidence: 0.88 },
  },
];

// The pairwise-edge count a binary graph would need to (incompletely) approximate
// an n-ary situation of k members: every member paired with every other.
export const binaryEdgeCount = (memberCount: number) => (memberCount * (memberCount - 1)) / 2;
