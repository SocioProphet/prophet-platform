/**
 * Warrant model — the proof chain, made renderable.
 *
 * These types are a STRUCTURAL MIRROR of shapes that already exist server-side. They are
 * copied field-for-field, not invented, so the cockpit cannot drift from the engine. Each
 * block names its upstream source; if the source moves, this file is the one place to fix.
 *
 *   • Plan / provenance / sense metric — hellgraph `ts/src/nlq.ts` @ v0.4.45
 *     (the NLQ typed-plan compiler, spec docs/specs/15_NLQ_Typed_Plan_Compiler_v0_1.md).
 *   • Admissibility ruling      — hellgraph `ts/src/claim-admissibility.ts` @ v0.4.45.
 *   • Receipt verify walk       — compute-gateway `engine_receipts.py::verify_walk`,
 *     served by `GET /v1/engine-receipts/{receipt_id}/verify`.
 *   • Seal outcome              — hellgraph-service `src/membrane.ts::SealOutcome` and
 *     `src/spine.ts::SpineResult` (the honest-degradation contract).
 *
 * The cockpit consumes; it does not define. HellGraph is not this app's lane to edit.
 */

// ─── Plan compiler: token spans ────────────────────────────────────────────────
// hellgraph ts/src/nlq.ts :361

/** Character offsets into the question, `[start, end)`, plus the tokens covered. */
export interface TokenSpan {
  start: number;
  end: number;
  /** The question text covered by the span. */
  text: string;
  /** Token stream positions covered, ascending. */
  tokenIndices: number[];
}

// ─── Admissibility (the creativity penalty's mechanism) ────────────────────────
// hellgraph ts/src/claim-admissibility.ts :105

export type AdmissibilityGate =
  | 'relevance'
  | 'authentication'
  | 'hearsay'
  | 'opinion'
  | 'prejudice';

export interface GateStep {
  gate: AdmissibilityGate;
  passed: boolean;
  reason: string;
}

export interface AdmissibilityDecision {
  admitted: boolean;
  /** 1.0 by default; discounted by the opinion gate; 0 when excluded. */
  weight: number;
  /** One step per gate evaluated, in order. Stops at the excluding gate. */
  steps: GateStep[];
  /** The gate that excluded the claim, when `admitted === false`. */
  excludedAt?: AdmissibilityGate;
}

// ─── Plan nodes ────────────────────────────────────────────────────────────────
// hellgraph ts/src/nlq.ts :625-670

export type Cardinality = 'one' | 'many';
export type SideEffects = 'none' | 'effect-request';
export type BindingKind = 'annotation' | 'action' | 'default' | 'unbound';
export type GroundingKind = 'token-span' | 'registry-default' | 'ungrounded';
export type UngroundedReason = 'no-token-span' | 'unbound-required-input';

/** Witness that a bound type satisfies a declared slot type — the subsumption that licensed the bind. */
export interface SubsumptionWitness {
  concept: string;
  satisfies: string;
  /** True when the types are identical; false when subsumption did the work (polymorphism). */
  direct: boolean;
}

export interface PlanGrounding {
  kind: GroundingKind;
  tokenSpan?: TokenSpan;
  conceptRef?: string;
  /** Annotator that grounded the node (`kind: 'token-span'`). */
  source?: string;
  confidence?: number;
  /** Registry default that grounded the node (`kind: 'registry-default'`). */
  defaultLabel?: string;
  /** Why the node counts as invented (`kind: 'ungrounded'`). */
  reason?: UngroundedReason;
  /** Admissibility ruling on an ungrounded node, filed as a `model-generated` claim. */
  admissibility?: AdmissibilityDecision;
}

export interface PlanBinding {
  /** Declared input name. */
  input: string;
  typeRef: string;
  cardinality: Cardinality;
  required: boolean;
  kind: BindingKind;
  conceptRef?: string;
  tokenSpan?: TokenSpan;
  /** Literal value lifted straight out of the question text. */
  literal?: string;
  defaultLabel?: string;
  /** Sub-plan producing this input (`kind: 'action'`). */
  via?: PlanNode;
  subsumption?: SubsumptionWitness;
}

export interface PlanNode {
  /** Deterministic path id: `n0`, `n0.items`, `n0.items.list`, … */
  nodeId: string;
  actionId: string;
  actionName: string;
  outputTypeRef: string;
  outputCardinality: Cardinality;
  sideEffects: SideEffects;
  grounding: PlanGrounding;
  bindings: PlanBinding[];
  effectRequest?: EffectRequestProposal;
}

/** A proposed effect — never executed at search time. Emitted only for effect-request leaves. */
export interface EffectRequestProposal {
  executorRef: string;
  proposes: string;
  arguments: { input: string; conceptRef?: string; literal?: string; tokenSpan?: TokenSpan }[];
  /** Always `proposed`: an EffectDecision must precede any world change. */
  status: 'proposed';
}

/** Pre-order (root first) walk of a plan tree. Mirrors `planNodes` in nlq.ts :673. */
export function planNodes(node: PlanNode): PlanNode[] {
  const out: PlanNode[] = [node];
  for (const b of node.bindings) if (b.via) out.push(...planNodes(b.via));
  return out;
}

// ─── Sense metric (W11.3's three axes) ─────────────────────────────────────────
// hellgraph ts/src/nlq.ts :681-712

export interface SenseWeights {
  coverage: number;
  groundedness: number;
  similarity: number;
}

/** hellgraph ts/src/nlq.ts :687 — the shipped default weighting. */
export const DEFAULT_SENSE_WEIGHTS: Readonly<SenseWeights> = Object.freeze({
  coverage: 0.5,
  groundedness: 0.3,
  similarity: 0.2,
});

export interface SenseMetric {
  /** Content tokens the plan consumes, over content tokens available. */
  coverage: number;
  /** Mean admissibility-discounted node weight; 1.0 when every node is grounded. */
  groundedness: number;
  /** `1 − groundedness`. The invention penalty, expressed as the admissibility discount. */
  creativity: number;
  /** Pre-order/left-to-right concordance of the spans the plan consumes. */
  similarity: number;
  /** `coverage·w.coverage + groundedness·w.groundedness + similarity·w.similarity`. */
  composite: number;
  weights: SenseWeights;
  contentTokens: number;
  consumedContentTokens: number;
  nodes: number;
  groundedNodes: number;
  ungroundedNodes: number;
  /** One entry per ungrounded node — the admissibility ruling that produced its discount. */
  admissibility: { nodeId: string; actionId: string; reason: UngroundedReason; weight: number }[];
}

/** Per-node provenance: token span → concept → action. hellgraph ts/src/nlq.ts :715 */
export interface NodeProvenance {
  nodeId: string;
  actionId: string;
  actionName: string;
  tokenSpan?: TokenSpan;
  conceptRef?: string;
  source?: string;
  grounded: boolean;
  /** Contribution to groundedness: 1.0 grounded, else the admissibility discount. */
  weight: number;
}

export interface PlanVariant {
  plan: PlanNode;
  senseMetric: SenseMetric;
  /** 1-based rank in the composite ordering. */
  rank: number;
  provenance: NodeProvenance[];
}

/** Identity of the contract every registered action validated against. nlq.ts :120 */
export interface ContractRef {
  schema: string;
  specVersion: string;
  sha256: string;
}

/** hellgraph ts/src/nlq.ts :314 */
export interface Token {
  text: string;
  norm: string;
  start: number;
  end: number;
  index: number;
  /** Function word — excluded from the coverage denominator. */
  stop: boolean;
}

/** hellgraph ts/src/nlq.ts :371 */
export interface TokenAnnotation {
  tokenSpan: TokenSpan;
  conceptRef: string;
  source: string;
  confidence: number;
}

export interface NlqCompilation {
  question: string;
  method: string;
  contract: ContractRef;
  tokens: Token[];
  annotations: TokenAnnotation[];
  /** `seq` = the store's monotonic logical clock — the receipt's real binding to graph state. */
  snapshot: { seq: number; nodes: number; edges: number };
  weights: SenseWeights;
  /** Ranked best-first. */
  variants: PlanVariant[];
  /** `variants[0]`, or null when nothing type-checked. */
  winner: PlanVariant | null;
  /** sha256 over the ranked output + snapshot + contract digest (proof-carrying). */
  hash: string;
}

// ─── Receipt verify walk ───────────────────────────────────────────────────────
// compute-gateway engine_receipts.py::verify_walk, served by
// GET /v1/engine-receipts/{receipt_id}/verify

/**
 * `_WALK` is pinned in engine_receipts.py :262 in exactly this order. The walk stops at the
 * first failure, so every later step comes back `skipped` — that attribution is the point,
 * and the UI renders it rather than collapsing it to one boolean.
 */
export const RECEIPT_WALK_STEPS = [
  'gateway-signature',
  'engine-seal-hash',
  'snapshot-seq-binding',
] as const;

export type ReceiptWalkStepName = (typeof RECEIPT_WALK_STEPS)[number];

/** Note: `skipped`, NOT `skip` — engine_receipts.py :313. */
export type ReceiptWalkStatus = 'ok' | 'fail' | 'skipped';

export interface ReceiptWalkStep {
  /** Field is `step` (not `name`/`id`) — engine_receipts.py :312. */
  step: string;
  status: ReceiptWalkStatus;
  /** Failure text lives here; there is no separate `error` key. May be null. */
  detail: string | null;
}

/** Exactly the four keys `verify_walk` returns. `receipt_id` is snake_case upstream. */
export interface ReceiptVerifyWalk {
  valid: boolean;
  receipt_id: string;
  project: string;
  /** Always length 3. */
  steps: ReceiptWalkStep[];
}

/** Plain-English gloss of what each step actually proves, for the receipt-walk view. */
export const WALK_STEP_MEANING: Record<string, string> = {
  'gateway-signature':
    'The receipt is genuinely ON the chain: every id-hash and prev-link re-derived from genesis, plus an Ed25519 signature over the in-toto statement.',
  'engine-seal-hash':
    "The engine's sealed sha256 recomputes byte-exactly from the stored receipt (canonical key order, hash field excluded).",
  'snapshot-seq-binding':
    'The receipt is pinned to the graph state it was cut from: snapshot.seq matches the sealed binding, and the signed outputs_sha still covers the stored envelope.',
};

// ─── Honest degradation ────────────────────────────────────────────────────────
// hellgraph-service src/membrane.ts::SealOutcome :200 and src/spine.ts::SpineResult :33

/**
 * The membrane's seal outcome. `sealError` is camelCase with a capital E — that exact
 * spelling is load-bearing; it is what `POST /api/membrane/decide` returns.
 *
 * The whole contract: when the gateway is unconfigured, unreachable, or refuses, the
 * service still answers — with `sealed: false` and a NON-NULL `sealError`. The UI's job
 * is to make that visible, never to paper over it.
 */
export interface SealOutcome {
  sealed: boolean;
  receiptRef: string | null;
  /** e.g. `gateway_unconfigured`, `gateway_503:…`, `gateway_unreachable:…`. Null on success. */
  sealError: string | null;
}

/** The engine-receipt spine result attached to /api/graph/enrich | /explore. */
export type SpineResult = { ok: true; receiptId: string } | { ok: false; reason: string };

/** Normalize a `spine` field onto the seal vocabulary so one badge renders both contracts. */
export function sealFromSpine(spine: SpineResult): SealOutcome {
  return spine.ok
    ? { sealed: true, receiptRef: spine.receiptId, sealError: null }
    : { sealed: false, receiptRef: null, sealError: spine.reason };
}

// ─── The normalized warrant the <Warrant> primitive renders ────────────────────

/**
 * Seal state at a glance. Three values, because "we could not check" and "we checked and
 * it failed" are different facts and collapsing them is exactly the dishonesty this
 * component exists to prevent.
 */
export type WarrantSealState = 'sealed' | 'unsealed' | 'unknown';

/** How a claim earned its place — the warrant TYPE, distinct from whether it is sealed. */
export type WarrantKind = GroundingKind | 'receipt';

export interface WarrantInput {
  /** What is being asserted. */
  claim: string;
  /** The plan node's grounding, when the claim came out of the NLQ compiler. */
  grounding?: PlanGrounding;
  /** The seal outcome, when the claim rode a membrane decision or a graph spine result. */
  seal?: SealOutcome;
  /** The full three-step verify walk, when the receipt has been walked. */
  walk?: ReceiptVerifyWalk;
  /** Receipt id, when known but not yet walked. */
  receiptRef?: string;
}

export interface WarrantView {
  claim: string;
  kind: WarrantKind;
  /** Short label for the warrant type, e.g. "token span", "model-generated". */
  kindLabel: string;
  /** One sentence on what this warrant type means. */
  kindBlurb: string;
  seal: WarrantSealState;
  sealLabel: string;
  /** Why it is unsealed — the `sealError`, or the failing walk step's detail. Null when sealed. */
  sealDetail: string | null;
  /** Epistemic-ramp mode this warrant maps onto (drives the --epi-* token). */
  epistemic: 'observed' | 'derived' | 'hypothesis' | 'attested' | 'unknown';
  /** The source span the claim points back at, when it has one. */
  span: TokenSpan | null;
  receiptRef: string | null;
  walk: ReceiptVerifyWalk | null;
  /** Admissibility ruling, present only for ungrounded (model-generated) claims. */
  admissibility: AdmissibilityDecision | null;
}

const KIND_META: Record<WarrantKind, { label: string; blurb: string; epistemic: WarrantView['epistemic'] }> = {
  'token-span': {
    label: 'token span',
    blurb: 'Grounded in the question itself — the claim points back at the exact characters that evoked it.',
    epistemic: 'observed',
  },
  'registry-default': {
    label: 'registry default',
    blurb: 'Supplied by an ambient typed value the registry vouches for, not by the question text.',
    epistemic: 'derived',
  },
  ungrounded: {
    label: 'model-generated',
    blurb: 'Invented, not grounded. Filed as a model-generated claim and discounted by the admissibility gate.',
    epistemic: 'hypothesis',
  },
  receipt: {
    label: 'sealed receipt',
    blurb: 'Warranted by a receipt on the gateway chain rather than by a plan node.',
    epistemic: 'attested',
  },
};

const SEAL_LABEL: Record<WarrantSealState, string> = {
  sealed: 'sealed',
  unsealed: 'UNSEALED',
  unknown: 'unknown',
};

/**
 * Resolve the badge state. Order matters, and it is deliberately pessimistic:
 *
 *  1. A walk that ran is the strongest evidence — `valid: false` means UNSEALED even if a
 *     `seal.sealed === true` claims otherwise. A seal is a claim; a walk is a check.
 *  2. `sealed: false` is ALWAYS unsealed, with `sealError` carried through as the reason.
 *     Never rendered as merely absent, never as silently fine.
 *  3. Nothing to go on renders `unknown` — which is honest, and is NOT the same as sealed.
 */
export function resolveSeal(input: WarrantInput): {
  state: WarrantSealState;
  detail: string | null;
} {
  const { walk, seal } = input;
  if (walk) {
    if (walk.valid) return { state: 'sealed', detail: null };
    const failed = walk.steps.find((s) => s.status === 'fail');
    return {
      state: 'unsealed',
      detail: failed
        ? `${failed.step}: ${failed.detail ?? 'failed with no detail'}`
        : 'verify walk returned invalid',
    };
  }
  if (seal) {
    if (seal.sealed) return { state: 'sealed', detail: null };
    return { state: 'unsealed', detail: seal.sealError ?? 'sealed:false with no sealError reported' };
  }
  return { state: 'unknown', detail: null };
}

/** Build the full renderable view. The one normalization every W11 surface goes through. */
export function warrantView(input: WarrantInput): WarrantView {
  const kind: WarrantKind = input.grounding ? input.grounding.kind : 'receipt';
  const meta = KIND_META[kind];
  const { state, detail } = resolveSeal(input);
  const g = input.grounding;
  return {
    claim: input.claim,
    kind,
    kindLabel: meta.label,
    kindBlurb: meta.blurb,
    seal: state,
    sealLabel: SEAL_LABEL[state],
    sealDetail: detail,
    // An unsealed claim never gets to keep an attested/observed ramp colour — the ramp
    // must degrade with the seal, or the colour lies about the proof.
    epistemic: state === 'unsealed' ? 'unknown' : state === 'sealed' && kind === 'receipt' ? 'attested' : meta.epistemic,
    span: g?.tokenSpan ?? null,
    receiptRef: input.receiptRef ?? input.walk?.receipt_id ?? input.seal?.receiptRef ?? null,
    walk: input.walk ?? null,
    admissibility: g?.admissibility ?? null,
  };
}

/** Format a [0,1] score as a percentage string with no decimals. */
export function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}
