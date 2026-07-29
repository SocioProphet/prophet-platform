/**
 * W11.6 — expertise-adaptive depth (DARPA TA-E).
 *
 * The same answer, rendered at the depth its consumer can use: novice / journeyman / expert.
 * Progressive disclosure bound to a STORED preference (see `stores/settings.ts`), not a
 * per-page toggle that nobody ever flips.
 *
 * ── THE ONE RULE ───────────────────────────────────────────────────────────────────────────
 * Depth changes what is SHOWN. It never changes what is CLAIMED.
 *
 * A novice view may hide the evidence URNs, the span arithmetic and the normalization regime.
 * It may NOT make a weak warrant look strong. That is not a style guideline here — it is
 * enforced two ways, both testable:
 *
 *   1. `DepthPolicy` only ever gates SUPPORTING detail. There is deliberately no flag capable
 *      of hiding a warrant type, a seal state, or a model-generated marker, so no future edit
 *      can turn one off by flipping a boolean. What is not expressible cannot regress.
 *
 *   2. Every plain-language gloss declares the strength it CONVEYS, and `WARRANT_STRENGTH`
 *      declares the strength the warrant actually HAS. `src/__tests__/expertiseDepth.test.ts`
 *      asserts they are equal for every (kind × level) pair. A gloss that flattered its
 *      warrant would fail the suite rather than ship.
 *
 * Note the asymmetry that follows from the rule: glossing DOWN is safe, glossing UP is not.
 * The novice text for `model-generated` is blunter than the expert text, not softer.
 */
import type { WarrantKind } from '../warrant/types';

export type Expertise = 'novice' | 'journeyman' | 'expert';

/** Ordered shallow → deep. The stored preference is one of these. */
export const EXPERTISE_LEVELS: readonly Expertise[] = ['novice', 'journeyman', 'expert'] as const;

export function isExpertise(v: unknown): v is Expertise {
  return typeof v === 'string' && (EXPERTISE_LEVELS as readonly string[]).includes(v);
}

/**
 * Ordinal epistemic strength of a warrant kind. Higher = a stronger claim on truth.
 *
 * This is the yardstick the gloss test measures against, so it is deliberately coarse and
 * explicit rather than derived from the ramp colour — colour must follow proof, not define it.
 *
 *   3  the source (or the chain) vouches for it directly
 *   2  derived from things that are vouched for
 *   0  produced by a model; the source does not support it
 */
export const WARRANT_STRENGTH: Record<WarrantKind, number> = {
  // source- or chain-warranted
  'direct-quote': 3,
  'token-span': 3,
  receipt: 3,
  // derived from warranted inputs
  computed: 2,
  inferred: 2,
  'registry-default': 2,
  // invented
  'model-generated': 0,
  ungrounded: 0,
};

/**
 * What a given depth reveals. EVERY field here is supporting detail.
 *
 * Warrant type, seal state, the unsealed reason and the model-generated marker are absent by
 * design: they are unconditional, so there is no switch to get wrong.
 */
export interface DepthPolicy {
  level: Expertise;
  /** 0 novice … 2 expert. */
  rank: number;
  label: string;
  /** What this level is for, shown next to the control. */
  blurb: string;
  /** Raw URNs, content hashes, receipt ids. */
  showRawRefs: boolean;
  /** `[start,end)` character arithmetic. */
  showSpanOffsets: boolean;
  /** The warrant's cited evidence refs, itemized. */
  showEvidenceList: boolean;
  /** Typed provenance chain links (derived_from, extracted_by, supersedes). */
  showProvenanceChain: boolean;
  /** Policy labels attached by producers or the policy fabric. */
  showPolicyLabels: boolean;
  /** The normalized machine-readable payload + its normalization regime. */
  showCanonicalPayload: boolean;
  /** W11.4: the competing concepts a span carried beyond the one the plan bound. */
  showLosingCandidates: boolean;
  /** Numeric confidences and annotator names. */
  showConfidence: boolean;
  /** Truncate long nugget text to this many characters; null = never truncate. */
  maxTextChars: number | null;
}

const POLICIES: Record<Expertise, DepthPolicy> = {
  novice: {
    level: 'novice',
    rank: 0,
    label: 'Novice',
    blurb: 'The claim and how far to trust it. Supporting detail stays folded away.',
    showRawRefs: false,
    showSpanOffsets: false,
    showEvidenceList: false,
    showProvenanceChain: false,
    showPolicyLabels: false,
    showCanonicalPayload: false,
    showLosingCandidates: false,
    showConfidence: false,
    maxTextChars: 240,
  },
  journeyman: {
    level: 'journeyman',
    rank: 1,
    label: 'Journeyman',
    blurb: 'Adds the evidence, the competing readings, and stated confidence.',
    showRawRefs: false,
    showSpanOffsets: true,
    showEvidenceList: true,
    showProvenanceChain: false,
    showPolicyLabels: true,
    showCanonicalPayload: false,
    showLosingCandidates: true,
    showConfidence: true,
    maxTextChars: 600,
  },
  expert: {
    level: 'expert',
    rank: 2,
    label: 'Expert',
    blurb: 'Everything on the record: URNs, hashes, provenance chain, normalization regime.',
    showRawRefs: true,
    showSpanOffsets: true,
    showEvidenceList: true,
    showProvenanceChain: true,
    showPolicyLabels: true,
    showCanonicalPayload: true,
    showLosingCandidates: true,
    showConfidence: true,
    maxTextChars: null,
  },
};

export function depthPolicy(level: Expertise): DepthPolicy {
  return POLICIES[level] ?? POLICIES.novice;
}

/** A depth-appropriate wording, plus the epistemic strength it claims to convey. */
export interface WarrantGloss {
  text: string;
  /** MUST equal WARRANT_STRENGTH[kind]. Proven by test, for every kind × level. */
  conveys: number;
}

/**
 * Plain-language readings of each warrant kind, per depth.
 *
 * Read the `model-generated` row: the novice wording is the bluntest of the three. That is the
 * asymmetry the rule demands — when in doubt, a shallower view must warn harder, not softer.
 */
const GLOSSES: Record<WarrantKind, Record<Expertise, string>> = {
  'direct-quote': {
    novice: 'Quoted word-for-word from the source.',
    journeyman: 'The exact source span, cut from the document — the source itself warrants it.',
    expert: 'direct-quote: text is byte-identical to sourceRef.span over the hashed source state.',
  },
  'token-span': {
    novice: 'Taken straight from the words you asked.',
    journeyman: 'Grounded in the question text — it points back at the characters that evoked it.',
    expert: 'token-span grounding: conceptRef bound from an annotated span of the question.',
  },
  receipt: {
    novice: 'Backed by a tamper-evident record.',
    journeyman: 'Warranted by a receipt on the gateway chain rather than by a plan node.',
    expert: 'receipt warrant: in-toto statement on the gateway chain, Ed25519-signed, seq-bound.',
  },
  computed: {
    novice: 'Worked out from numbers stated in the source.',
    journeyman: 'Calculated from cited source values under a declared normalization regime.',
    expert: 'computed: deterministic normalization over cited values; regime declared in canonicalPayload.',
  },
  inferred: {
    novice: 'Reasoned from things the source says — a step beyond quoting.',
    journeyman: 'Follows by stated inference from cited premises. The premises are warranted; this step is reasoning.',
    expert: 'inferred: entailment from cited premises; schema requires ≥1 evidence ref.',
  },
  'registry-default': {
    novice: 'Filled in from a standard setting, not from your question.',
    journeyman: 'Supplied by an ambient typed value the registry vouches for, not by the question text.',
    expert: 'registry-default grounding: slot filled from a registered default; no token span.',
  },
  'model-generated': {
    novice: 'Written by the AI. It is NOT in the source — treat it as a suggestion.',
    journeyman: 'Produced by a model from the source window, and not warranted by it. Discounted wherever used.',
    expert: 'model-generated: unwarranted by sourceRef; admissibility-discounted, never launderable.',
  },
  ungrounded: {
    novice: 'Invented by the planner. Nothing in your question asked for it.',
    journeyman: 'Not grounded in the question. Filed as a model-generated claim and discounted by the admissibility gate.',
    expert: 'ungrounded grounding: no token span; admissibility ruling carries the discount.',
  },
};

/** The gloss for a warrant kind at a depth, tagged with the strength it conveys. */
export function warrantGloss(kind: WarrantKind, level: Expertise): WarrantGloss {
  const byLevel = GLOSSES[kind];
  // An unknown kind must never borrow a confident gloss. Strength 0, and it says so.
  if (!byLevel) return { text: 'Unrecognized warrant — treated as unproven.', conveys: 0 };
  return { text: byLevel[level] ?? byLevel.novice, conveys: WARRANT_STRENGTH[kind] ?? 0 };
}

/** Truncate to the depth's budget, on a word boundary, with an explicit ellipsis. */
export function clampText(text: string, policy: DepthPolicy): { text: string; truncated: boolean } {
  const max = policy.maxTextChars;
  if (max === null || text.length <= max) return { text, truncated: false };
  const cut = text.slice(0, max);
  const sp = cut.lastIndexOf(' ');
  return { text: (sp > max * 0.6 ? cut.slice(0, sp) : cut).trimEnd() + '…', truncated: true };
}
