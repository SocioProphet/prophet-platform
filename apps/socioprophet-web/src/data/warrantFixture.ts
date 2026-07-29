/**
 * Deterministic, offline-safe fixture for the W11 warrant surfaces.
 *
 * WHY A FIXTURE: the NLQ typed-plan compiler ships in the hellgraph ENGINE
 * (`ts/src/nlq.ts`, landed in v0.4.44 — `compileQuestion`). Nothing in
 * prophet-platform exposes it over HTTP yet: there is no `/svc/nlq` route, no
 * hellgraph-service handler, and no gateway endpoint. So these surfaces are built
 * against the REAL types (mirrored field-for-field in ../features/warrant/types)
 * and fed by this fixture until a compile endpoint exists. When one lands, only
 * `compileQuestion()` in ../services/warrantApi.ts changes — no component does.
 *
 * The numbers below are internally consistent, not decorative:
 *   composite = coverage·0.5 + groundedness·0.3 + similarity·0.2   (DEFAULT_SENSE_WEIGHTS)
 *   creativity = 1 − groundedness
 *   groundedness = mean admissibility-discounted node weight
 * `src/__tests__/warrantFixture.test.ts` re-derives every one of them, so the
 * fixture cannot drift into telling a story the engine's arithmetic would not.
 */
import {
  DEFAULT_SENSE_WEIGHTS,
  type NlqCompilation,
  type PlanVariant,
  type ReceiptVerifyWalk,
  type SealOutcome,
  type TokenSpan,
  type Token,
} from '../features/warrant/types';

export const FIXTURE_QUESTION = 'how many suppliers in Germany are delayed';

/** Character offsets are real offsets into FIXTURE_QUESTION — every span slices back exactly. */
const SPAN = {
  howMany: { start: 0, end: 8, text: 'how many', tokenIndices: [0, 1] },
  suppliers: { start: 9, end: 18, text: 'suppliers', tokenIndices: [2] },
  germany: { start: 22, end: 29, text: 'Germany', tokenIndices: [4] },
  delayed: { start: 34, end: 41, text: 'delayed', tokenIndices: [6] },
} satisfies Record<string, TokenSpan>;

/**
 * Tokenized exactly as `tokenizeQuestion` would: Unicode letter/number runs, `stop` set from
 * NLQ_STOP_WORDS. Note `how` and `many` are deliberately NOT stop words — quantity words are
 * what select a counting action, so they count toward coverage.
 */
export const FIXTURE_TOKENS: Token[] = [
  { text: 'how', norm: 'how', start: 0, end: 3, index: 0, stop: false },
  { text: 'many', norm: 'many', start: 4, end: 8, index: 1, stop: false },
  { text: 'suppliers', norm: 'suppliers', start: 9, end: 18, index: 2, stop: false },
  { text: 'in', norm: 'in', start: 19, end: 21, index: 3, stop: true },
  { text: 'Germany', norm: 'germany', start: 22, end: 29, index: 4, stop: false },
  { text: 'are', norm: 'are', start: 30, end: 33, index: 5, stop: true },
  { text: 'delayed', norm: 'delayed', start: 34, end: 41, index: 6, stop: false },
];

/** 5 content tokens: how, many, suppliers, Germany, delayed. */
const CONTENT_TOKENS = 5;

// ── variant 1 (winner) — every node grounded in the question text ────────────────
const V1: PlanVariant = {
  rank: 1,
  plan: {
    nodeId: 'n0',
    actionId: 'urn:srcos:action:Count',
    actionName: 'Count',
    outputTypeRef: 'urn:srcos:type:Cardinal',
    outputCardinality: 'one',
    sideEffects: 'none',
    grounding: {
      kind: 'token-span',
      tokenSpan: SPAN.howMany,
      conceptRef: 'urn:srcos:action:Count',
      source: 'lexicon',
      confidence: 0.94,
    },
    bindings: [
      {
        input: 'items',
        typeRef: 'urn:srcos:type:Supplier',
        cardinality: 'many',
        required: true,
        kind: 'action',
        conceptRef: 'urn:srcos:type:Supplier',
        via: {
          nodeId: 'n0.items',
          actionId: 'urn:srcos:action:FilterByStatus',
          actionName: 'FilterByStatus',
          outputTypeRef: 'urn:srcos:type:Supplier',
          outputCardinality: 'many',
          sideEffects: 'none',
          grounding: {
            kind: 'token-span',
            tokenSpan: SPAN.delayed,
            conceptRef: 'urn:srcos:concept:DelayedStatus',
            source: 'lexicon',
            confidence: 0.88,
          },
          bindings: [
            {
              input: 'source',
              typeRef: 'urn:srcos:type:Supplier',
              cardinality: 'many',
              required: true,
              kind: 'action',
              conceptRef: 'urn:srcos:type:Supplier',
              via: {
                nodeId: 'n0.items.source',
                actionId: 'urn:srcos:action:SuppliersInRegion',
                actionName: 'SuppliersInRegion',
                outputTypeRef: 'urn:srcos:type:Supplier',
                outputCardinality: 'many',
                sideEffects: 'none',
                grounding: {
                  kind: 'token-span',
                  tokenSpan: SPAN.suppliers,
                  conceptRef: 'urn:srcos:type:Supplier',
                  source: 'lexicon',
                  confidence: 0.97,
                },
                bindings: [
                  {
                    input: 'region',
                    typeRef: 'urn:srcos:type:Region',
                    cardinality: 'one',
                    required: true,
                    kind: 'annotation',
                    conceptRef: 'urn:srcos:concept:Germany',
                    tokenSpan: SPAN.germany,
                    literal: 'Germany',
                    subsumption: {
                      concept: 'urn:srcos:concept:Germany',
                      satisfies: 'urn:srcos:type:Region',
                      direct: false,
                    },
                  },
                ],
              },
            },
            {
              input: 'status',
              typeRef: 'urn:srcos:nlq:Literal',
              cardinality: 'one',
              required: true,
              kind: 'annotation',
              conceptRef: 'urn:srcos:concept:DelayedStatus',
              tokenSpan: SPAN.delayed,
              literal: 'delayed',
            },
          ],
        },
      },
    ],
  },
  senseMetric: {
    coverage: 1,
    groundedness: 1,
    creativity: 0,
    similarity: 0.5,
    composite: 0.9, // 1·0.5 + 1·0.3 + 0.5·0.2
    weights: DEFAULT_SENSE_WEIGHTS,
    contentTokens: CONTENT_TOKENS,
    consumedContentTokens: 5,
    nodes: 3,
    groundedNodes: 3,
    ungroundedNodes: 0,
    admissibility: [],
  },
  provenance: [
    {
      nodeId: 'n0',
      actionId: 'urn:srcos:action:Count',
      actionName: 'Count',
      tokenSpan: SPAN.howMany,
      conceptRef: 'urn:srcos:action:Count',
      source: 'lexicon',
      grounded: true,
      weight: 1,
    },
    {
      nodeId: 'n0.items',
      actionId: 'urn:srcos:action:FilterByStatus',
      actionName: 'FilterByStatus',
      tokenSpan: SPAN.delayed,
      conceptRef: 'urn:srcos:concept:DelayedStatus',
      source: 'lexicon',
      grounded: true,
      weight: 1,
    },
    {
      nodeId: 'n0.items.source',
      actionId: 'urn:srcos:action:SuppliersInRegion',
      actionName: 'SuppliersInRegion',
      tokenSpan: SPAN.suppliers,
      conceptRef: 'urn:srcos:type:Supplier',
      source: 'lexicon',
      grounded: true,
      weight: 1,
    },
  ],
};

// ── variant 2 — ignored "delayed" and INVENTED a risk ranking. Lost on coverage ──
const V2: PlanVariant = {
  rank: 2,
  plan: {
    nodeId: 'n0',
    actionId: 'urn:srcos:action:Count',
    actionName: 'Count',
    outputTypeRef: 'urn:srcos:type:Cardinal',
    outputCardinality: 'one',
    sideEffects: 'none',
    grounding: {
      kind: 'token-span',
      tokenSpan: SPAN.howMany,
      conceptRef: 'urn:srcos:action:Count',
      source: 'lexicon',
      confidence: 0.94,
    },
    bindings: [
      {
        input: 'items',
        typeRef: 'urn:srcos:type:Supplier',
        cardinality: 'many',
        required: true,
        kind: 'action',
        conceptRef: 'urn:srcos:type:Supplier',
        via: {
          nodeId: 'n0.items',
          actionId: 'urn:srcos:action:RankByRisk',
          actionName: 'RankByRisk',
          outputTypeRef: 'urn:srcos:type:Supplier',
          outputCardinality: 'many',
          sideEffects: 'none',
          grounding: {
            kind: 'ungrounded',
            reason: 'no-token-span',
            admissibility: {
              admitted: true,
              weight: 0.5, // OPINION_WEIGHT_MULTIPLIER
              steps: [
                { gate: 'relevance', passed: true, reason: 'bears on the requested supplier set' },
                { gate: 'authentication', passed: true, reason: 'action is registry-registered' },
                { gate: 'hearsay', passed: true, reason: 'depth 0 — asserted directly by the compiler' },
                {
                  gate: 'opinion',
                  passed: true,
                  reason: 'model-generated: admitted at the opinion discount (×0.5)',
                },
              ],
            },
          },
          bindings: [
            {
              input: 'source',
              typeRef: 'urn:srcos:type:Supplier',
              cardinality: 'many',
              required: true,
              kind: 'annotation',
              conceptRef: 'urn:srcos:type:Supplier',
              tokenSpan: SPAN.suppliers,
            },
            {
              input: 'region',
              typeRef: 'urn:srcos:type:Region',
              cardinality: 'one',
              required: false,
              kind: 'annotation',
              conceptRef: 'urn:srcos:concept:Germany',
              tokenSpan: SPAN.germany,
              literal: 'Germany',
            },
          ],
        },
      },
    ],
  },
  senseMetric: {
    coverage: 0.8, // 4 of 5 — "delayed" never consumed
    groundedness: 0.75, // (1 + 0.5) / 2
    creativity: 0.25,
    similarity: 1,
    composite: 0.825, // 0.8·0.5 + 0.75·0.3 + 1·0.2
    weights: DEFAULT_SENSE_WEIGHTS,
    contentTokens: CONTENT_TOKENS,
    consumedContentTokens: 4,
    nodes: 2,
    groundedNodes: 1,
    ungroundedNodes: 1,
    admissibility: [
      {
        nodeId: 'n0.items',
        actionId: 'urn:srcos:action:RankByRisk',
        reason: 'no-token-span',
        weight: 0.5,
      },
    ],
  },
  provenance: [
    {
      nodeId: 'n0',
      actionId: 'urn:srcos:action:Count',
      actionName: 'Count',
      tokenSpan: SPAN.howMany,
      conceptRef: 'urn:srcos:action:Count',
      source: 'lexicon',
      grounded: true,
      weight: 1,
    },
    {
      nodeId: 'n0.items',
      actionId: 'urn:srcos:action:RankByRisk',
      actionName: 'RankByRisk',
      grounded: false,
      weight: 0.5,
    },
  ],
};

// ── variant 3 — invented its root outright. Lost on groundedness ────────────────
const V3: PlanVariant = {
  rank: 3,
  plan: {
    nodeId: 'n0',
    actionId: 'urn:srcos:action:Summarize',
    actionName: 'Summarize',
    outputTypeRef: 'urn:srcos:type:Narrative',
    outputCardinality: 'one',
    sideEffects: 'none',
    grounding: {
      kind: 'ungrounded',
      reason: 'no-token-span',
      admissibility: {
        admitted: false,
        weight: 0,
        excludedAt: 'relevance',
        steps: [
          {
            gate: 'relevance',
            passed: false,
            reason: 'a narrative does not answer a cardinality question — below min relevance',
          },
        ],
      },
    },
    bindings: [
      {
        input: 'subject',
        typeRef: 'urn:srcos:type:Supplier',
        cardinality: 'many',
        required: true,
        kind: 'action',
        conceptRef: 'urn:srcos:type:Supplier',
        via: {
          nodeId: 'n0.subject',
          actionId: 'urn:srcos:action:DescribeRegion',
          actionName: 'DescribeRegion',
          outputTypeRef: 'urn:srcos:type:Supplier',
          outputCardinality: 'many',
          sideEffects: 'effect-request',
          grounding: {
            kind: 'ungrounded',
            reason: 'unbound-required-input',
            admissibility: {
              admitted: true,
              weight: 0.5,
              steps: [
                { gate: 'relevance', passed: true, reason: 'names the requested region' },
                { gate: 'authentication', passed: true, reason: 'action is registry-registered' },
                { gate: 'hearsay', passed: true, reason: 'depth 0' },
                { gate: 'opinion', passed: true, reason: 'model-generated: opinion discount (×0.5)' },
              ],
            },
          },
          effectRequest: {
            executorRef: 'urn:srcos:executor:RegionReport',
            proposes: 'urn:srcos:type:Supplier',
            arguments: [
              { input: 'region', conceptRef: 'urn:srcos:concept:Germany', literal: 'Germany', tokenSpan: SPAN.germany },
            ],
            status: 'proposed',
          },
          bindings: [
            {
              input: 'region',
              typeRef: 'urn:srcos:type:Region',
              cardinality: 'one',
              required: true,
              kind: 'annotation',
              conceptRef: 'urn:srcos:concept:Germany',
              tokenSpan: SPAN.germany,
              literal: 'Germany',
            },
            {
              input: 'entity',
              typeRef: 'urn:srcos:type:Supplier',
              cardinality: 'many',
              required: true,
              kind: 'unbound',
            },
          ],
        },
      },
    ],
  },
  senseMetric: {
    coverage: 0.8,
    groundedness: 0.25, // (0 + 0.5) / 2
    creativity: 0.75,
    similarity: 1,
    composite: 0.675, // 0.8·0.5 + 0.25·0.3 + 1·0.2
    weights: DEFAULT_SENSE_WEIGHTS,
    contentTokens: CONTENT_TOKENS,
    consumedContentTokens: 4,
    nodes: 2,
    groundedNodes: 0,
    ungroundedNodes: 2,
    admissibility: [
      {
        nodeId: 'n0',
        actionId: 'urn:srcos:action:Summarize',
        reason: 'no-token-span',
        weight: 0,
      },
      {
        nodeId: 'n0.subject',
        actionId: 'urn:srcos:action:DescribeRegion',
        reason: 'unbound-required-input',
        weight: 0.5,
      },
    ],
  },
  provenance: [
    {
      nodeId: 'n0',
      actionId: 'urn:srcos:action:Summarize',
      actionName: 'Summarize',
      grounded: false,
      weight: 0,
    },
    {
      nodeId: 'n0.subject',
      actionId: 'urn:srcos:action:DescribeRegion',
      actionName: 'DescribeRegion',
      tokenSpan: SPAN.germany,
      conceptRef: 'urn:srcos:concept:Germany',
      grounded: false,
      weight: 0.5,
    },
  ],
};

export const FIXTURE_COMPILATION: NlqCompilation = {
  question: FIXTURE_QUESTION,
  method: 'typed-plan-beam',
  contract: {
    schema: 'SemanticAction.json',
    specVersion: '0.1.0',
    sha256: 'sha256:4f1b9c2e8a7d6543210fedcba9876543210abcdef0123456789abcdef01234567',
  },
  tokens: FIXTURE_TOKENS,
  annotations: [
    { tokenSpan: SPAN.howMany, conceptRef: 'urn:srcos:action:Count', source: 'lexicon', confidence: 0.94 },
    { tokenSpan: SPAN.suppliers, conceptRef: 'urn:srcos:type:Supplier', source: 'lexicon', confidence: 0.97 },
    { tokenSpan: SPAN.germany, conceptRef: 'urn:srcos:concept:Germany', source: 'kko-semantic', confidence: 0.81 },
    { tokenSpan: SPAN.delayed, conceptRef: 'urn:srcos:concept:DelayedStatus', source: 'lexicon', confidence: 0.88 },
  ],
  snapshot: { seq: 41207, nodes: 128_940, edges: 411_663 },
  weights: DEFAULT_SENSE_WEIGHTS,
  variants: [V1, V2, V3],
  winner: V1,
  hash: 'sha256:9c1f0b7e5d3a86420fedcba98765432100abcdef123456789abcdef0123456789',
};

/** A receipt id shaped like the gateway's (sha256 of the receipt body). */
export const FIXTURE_RECEIPT_ID =
  'sha256:2b7d4e9a1c5f83600aabbccddeeff00112233445566778899aabbccddeeff0011';

/** All three steps ok — what a sealed compilation looks like. */
export const FIXTURE_WALK_VALID: ReceiptVerifyWalk = {
  valid: true,
  receipt_id: FIXTURE_RECEIPT_ID,
  project: 'default',
  steps: [
    {
      step: 'gateway-signature',
      status: 'ok',
      detail:
        'chain position 318 re-derived: every id-hash and prev-link from genesis to this receipt verified, + Ed25519 over the in-toto statement',
    },
    {
      step: 'engine-seal-hash',
      status: 'ok',
      detail: `sealed sha256 recomputed byte-exactly (${FIXTURE_RECEIPT_ID})`,
    },
    { step: 'snapshot-seq-binding', status: 'ok', detail: 'graph-state binding intact (seq 41207)' },
  ],
};

/**
 * A TAMPERED receipt: step 1 passes, step 2 fails, step 3 is `skipped` — the walk stops at the
 * first failure so tampering is attributed to the step that owns it. This is the honest-
 * degradation case the UI must render as visibly unsealed.
 */
export const FIXTURE_WALK_TAMPERED: ReceiptVerifyWalk = {
  valid: false,
  receipt_id: FIXTURE_RECEIPT_ID,
  project: 'default',
  steps: [
    {
      step: 'gateway-signature',
      status: 'ok',
      detail:
        'chain position 318 re-derived: every id-hash and prev-link from genesis to this receipt verified, + Ed25519 over the in-toto statement',
    },
    {
      step: 'engine-seal-hash',
      status: 'fail',
      detail:
        'engine sealed hash does not recompute: sealed sha256:2b7d4e9a…, recomputed sha256:8e0c1a55…',
    },
    { step: 'snapshot-seq-binding', status: 'skipped', detail: 'prior step failed' },
  ],
};

/** The membrane's degraded seal: the service answered, but the gateway never sealed it. */
export const FIXTURE_SEAL_DEGRADED: SealOutcome = {
  sealed: false,
  receiptRef: null,
  sealError: 'gateway_unconfigured',
};

export const FIXTURE_SEAL_OK: SealOutcome = {
  sealed: true,
  receiptRef: FIXTURE_RECEIPT_ID,
  sealError: null,
};
