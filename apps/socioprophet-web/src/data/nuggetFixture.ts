/**
 * Deterministic, offline-safe fixture for the W11.5 nugget feed.
 *
 * WHY A FIXTURE: a live door DOES exist (see `services/nuggetApi.ts` — nuggets land in
 * hellgraph-service as nodes labelled `KnowledgeNugget`, readable via
 * `GET /api/graph/query?label=KnowledgeNugget`), but it only returns anything once
 * `apps/nugget-extractor` has actually ingested a document into the graph the cockpit is
 * pointed at. In dev, in tests, and on any environment that has not run an extraction, the
 * feed falls back to THIS — and says so on screen, loudly, the way StudioWarrant does.
 *
 * The values are faithful to the producer, not decorative:
 *   • ids are content-addressed exactly as `contract.local_id` computes them —
 *     sha256(`${docRef}|${contentHash}`)[:12] + a 6-digit ordinal.
 *   • `contentHash` is the real sha256 of SOURCE_TEXT below, in the schema's
 *     `sha256-<64hex>` form.
 *   • every direct-quote's span satisfies the family validator's invariant
 *     `end - start === text.length`, and slices back out of SOURCE_TEXT byte-for-byte.
 *     `src/__tests__/nuggetFeed.test.ts` re-derives all of it.
 *   • `createdBy`, `specVersion` and the KKO type URIs are the producer's own constants.
 *
 * PRODUCER NOTE (deliberate, not an oversight): `apps/nugget-extractor` mints only
 * `direct-quote` and `computed` — its module docstring is explicit that it runs no inference
 * engine and calls no model. The `inferred` and `model-generated` entries below therefore
 * carry a DIFFERENT `createdBy`, because in the real system they would come from a producer
 * that does. Attributing them to the extractor would be a small lie in a fixture whose whole
 * job is to demonstrate honest attribution.
 */
import type { KnowledgeNugget } from '../features/nuggets/types';

/** The hashed source state every span below indexes into. */
export const FIXTURE_SOURCE_TEXT = [
  'Northwind Logistics Group — FY24 Annual Report (extract)',
  '',
  'Network revenue for FY24 was AUD 1,138.9m, up 22.6% on the prior corresponding period.',
  'Supply chain disruption in Germany delayed 14 shipments in the second half.',
  'The Group expects trading conditions to normalise during FY25.',
].join('\n');

export const FIXTURE_DOC_REF = 'urn:srcos:document:northwind-fy24-annual-report';

/** Real sha256 of FIXTURE_SOURCE_TEXT, in the schema's `sha256-<64hex>` form. */
export const FIXTURE_CONTENT_HASH =
  'sha256-cbc77923930d0aec9104ca4c8a7c2baf16926cb46b7f7c9aed9892ac112cb459';

const NUG = 'urn:srcos:knowledge-nugget:nug-9c70031e47ab-';
const EXTRACTOR = 'urn:srcos:agent:nugget-extractor';
const KKO_WRITTEN_INFO = 'http://kbpedia.org/ontologies/kko#WrittenInfo';
const KKO_QUANTITY = 'http://kbpedia.org/ontologies/kko#Quantity';
const RUN_REF = 'urn:srcos:run:nugget-extract-20260728T2214Z';
const REGIME = 'nugget-extractor/quantity@v1';

const src = (start: number, end: number) => ({
  docRef: FIXTURE_DOC_REF,
  span: { start, end },
  contentHash: FIXTURE_CONTENT_HASH,
});

/** N0 — a verbatim cut. confidence 1.0: a direct quote is not a guess. */
const N0: KnowledgeNugget = {
  id: `${NUG}000000`,
  type: 'KnowledgeNugget',
  specVersion: '0.1.0',
  sourceRef: src(58, 144),
  warrant: { type: 'direct-quote', evidence: [], confidence: 1 },
  text: 'Network revenue for FY24 was AUD 1,138.9m, up 22.6% on the prior corresponding period.',
  kkoTypeRefs: [KKO_WRITTEN_INFO],
  policyLabels: ['public-filing'],
  provenance: [{ rel: 'extracted_by', ref: RUN_REF }],
  createdBy: EXTRACTOR,
  wallTime: '2026-07-28T22:14:03.114Z',
  logicalTime: 1,
};

/**
 * N1 — a currency quantity, normalized. CITES N0: the value's warrant names the span it was
 * computed from. This is the production IFM lineage (document → typed value) the contract
 * generalizes.
 */
const N1: KnowledgeNugget = {
  id: `${NUG}000001`,
  type: 'KnowledgeNugget',
  specVersion: '0.1.0',
  sourceRef: src(87, 99),
  warrant: { type: 'computed', evidence: [N0.id], confidence: 1 },
  text: 'Normalized quantity: 1.1389e+09 AUD (from "AUD 1,138.9m").',
  kkoTypeRefs: [KKO_QUANTITY],
  canonicalPayload: {
    normalizationRegime: REGIME,
    kind: 'currency',
    value: 1138900000,
    unit: 'AUD',
    currencySymbol: null,
    scale: 'million',
    surface: 'AUD 1,138.9m',
  },
  policyLabels: ['public-filing'],
  provenance: [
    { rel: 'derived_from', ref: N0.id },
    { rel: 'extracted_by', ref: RUN_REF },
  ],
  createdBy: EXTRACTOR,
  wallTime: '2026-07-28T22:14:03.118Z',
  logicalTime: 2,
};

/** N2 — a percentage, same regime, also citing N0. */
const N2: KnowledgeNugget = {
  id: `${NUG}000002`,
  type: 'KnowledgeNugget',
  specVersion: '0.1.0',
  sourceRef: src(104, 109),
  warrant: { type: 'computed', evidence: [N0.id], confidence: 1 },
  text: 'Normalized quantity: 22.6 percent (from "22.6%").',
  kkoTypeRefs: [KKO_QUANTITY],
  canonicalPayload: {
    normalizationRegime: REGIME,
    kind: 'percentage',
    value: 22.6,
    unit: 'percent',
    currencySymbol: null,
    scale: null,
    surface: '22.6%',
  },
  policyLabels: ['public-filing'],
  provenance: [
    { rel: 'derived_from', ref: N0.id },
    { rel: 'extracted_by', ref: RUN_REF },
  ],
  createdBy: EXTRACTOR,
  wallTime: '2026-07-28T22:14:03.121Z',
  logicalTime: 3,
};

/** N3 — the second quote. */
const N3: KnowledgeNugget = {
  id: `${NUG}000003`,
  type: 'KnowledgeNugget',
  specVersion: '0.1.0',
  sourceRef: src(145, 220),
  warrant: { type: 'direct-quote', evidence: [], confidence: 1 },
  text: 'Supply chain disruption in Germany delayed 14 shipments in the second half.',
  kkoTypeRefs: [KKO_WRITTEN_INFO],
  policyLabels: ['public-filing'],
  provenance: [{ rel: 'extracted_by', ref: RUN_REF }],
  createdBy: EXTRACTOR,
  wallTime: '2026-07-28T22:14:03.124Z',
  logicalTime: 4,
};

/**
 * N4 — an INFERENCE from two cited quotes. Note the different producer: the extractor runs no
 * inference engine, so this could not have come from it.
 */
const N4: KnowledgeNugget = {
  id: `${NUG}000004`,
  type: 'KnowledgeNugget',
  specVersion: '0.1.0',
  sourceRef: src(145, 220),
  warrant: { type: 'inferred', evidence: [N0.id, N3.id], confidence: 0.71 },
  text: 'European distribution was a material drag on FY24 network revenue.',
  kkoTypeRefs: [KKO_WRITTEN_INFO],
  policyLabels: ['public-filing', 'analyst-derived'],
  provenance: [
    { rel: 'derived_from', ref: N0.id },
    { rel: 'derived_from', ref: N3.id },
    { rel: 'extracted_by', ref: 'urn:srcos:run:reasoning-council-20260728T2231Z' },
  ],
  createdBy: 'urn:srcos:agent:reasoning-council',
  wallTime: '2026-07-28T22:31:47.002Z',
  logicalTime: 5,
};

/**
 * N5 — MODEL-GENERATED. Evidence-free, which the schema permits precisely because this class
 * is admissibility-discounted regardless. Its `sourceRef.span` is the CONDITIONING WINDOW the
 * generation was given — it does not warrant the text, and the surface must not render it as
 * though it did.
 *
 * Its stated confidence (0.62) sits in the same range as the inferred nugget's (0.71), which
 * is the point: the two numbers are NOT comparable across warrant types. The schema is explicit
 * that admissibility keys on warrant.type first and confidence second, so no amount of stated
 * confidence promotes this out of the model-generated class.
 */
const N5: KnowledgeNugget = {
  id: `${NUG}000005`,
  type: 'KnowledgeNugget',
  specVersion: '0.1.0',
  sourceRef: src(221, 283),
  warrant: { type: 'model-generated', evidence: [], confidence: 0.62 },
  text: 'Management will likely consolidate European distribution into a single hub during FY25.',
  kkoTypeRefs: [KKO_WRITTEN_INFO],
  policyLabels: ['model-output'],
  provenance: [{ rel: 'extracted_by', ref: 'urn:srcos:run:summarizer-20260728T2240Z' }],
  createdBy: 'urn:srcos:agent:summarizer',
  wallTime: '2026-07-28T22:40:12.880Z',
  logicalTime: 6,
};

/** Newest first, the order the feed renders. */
export const FIXTURE_NUGGETS: KnowledgeNugget[] = [N5, N4, N3, N2, N1, N0];

/**
 * A payload that will NOT parse — carried so the feed's fail-closed path is demonstrable
 * rather than merely asserted. It is a `computed` warrant citing no evidence, which the
 * schema's if/then forbids. The feed shows it as unreadable, with the reason, and does not
 * render it as a nugget.
 */
export const FIXTURE_MALFORMED = {
  id: `${NUG}000009`,
  type: 'KnowledgeNugget',
  specVersion: '0.1.0',
  sourceRef: src(0, 56),
  warrant: { type: 'computed', evidence: [], confidence: 0.9 },
  text: 'Northwind Logistics Group — FY24 Annual Report (extract)',
  policyLabels: [],
  createdBy: EXTRACTOR,
  wallTime: '2026-07-28T22:14:03.130Z',
  logicalTime: 9,
};
