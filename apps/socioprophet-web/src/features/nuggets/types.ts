/**
 * KnowledgeNugget — the estate's L2 content grain, made renderable.
 *
 * STRUCTURAL MIRROR of `KnowledgeNugget.json` @ specVersion 0.1.0 (sourceos-spec #210, vendored
 * into `apps/nugget-extractor/src/nugget_extractor/schemas/`). Copied field-for-field, not
 * invented. The producer is `apps/nugget-extractor` (#1042).
 *
 * ── THE NORMATIVE RULE THIS FILE EXISTS TO KEEP ────────────────────────────────────────────
 * From the schema's own description:
 *
 *   "warrant.type = model-generated MUST remain visibly distinguishable on every downstream
 *    surface — retrieval, ranking, rendering, and admissibility weighting all discount
 *    model-generated nuggets relative to source-warranted ones, and no downstream transform
 *    may launder a model-generated nugget into a source-warranted one."
 *
 * So: no mapping in this file ever widens a warrant. Unparseable input becomes `unreadable`,
 * which is UNKNOWN — deliberately not "model-generated" (we did not establish that) and
 * deliberately not a failure verdict (we did not check anything). It is simply not readable,
 * and it says so.
 */
import type { NuggetWarrantType, TokenSpan, WarrantInput } from '../warrant/types';

export type { NuggetWarrantType };

/** KnowledgeNugget.json → sourceRef.span */
export interface NuggetSpan {
  /** 0-based inclusive character offset into the hashed source text. */
  start: number;
  /** 0-based exclusive offset. For direct-quote, `end - start === text.length` (validator-enforced). */
  end: number;
  /** 1-based page, for paginated sources. */
  page?: number;
}

/** KnowledgeNugget.json → sourceRef */
export interface NuggetSourceRef {
  /** URN of the governed source document. `urn:srcos:<kind>:<local-id>`. */
  docRef: string;
  /**
   * The span within the hashed source text. For `model-generated` this is the CONDITIONING
   * WINDOW the generation was given — per the schema, it does NOT warrant the text.
   */
  span: NuggetSpan;
  /** `sha256-<64 hex>`. Pins the nugget to an immutable source state so offsets cannot drift. */
  contentHash: string;
}

/** KnowledgeNugget.json → warrant */
export interface NuggetWarrant {
  type: NuggetWarrantType;
  /**
   * Evidence refs grounding the warrant. Schema invariant: `computed` and `inferred` MUST cite
   * at least one — a derivation with no cited inputs is not a derivation. `direct-quote` is
   * grounded by sourceRef itself; `model-generated` may be evidence-free, which is exactly why
   * it is admissibility-discounted.
   */
  evidence: string[];
  /**
   * Producer-stated confidence, 0..1. NOT admissibility: the schema is explicit that
   * admissibility is a function of warrant.type FIRST (model-generated is discounted whatever
   * its confidence) and confidence second. The UI must never let this number outrank the type.
   */
  confidence: number;
}

export interface NuggetProvenanceLink {
  /** e.g. derived_from, extracted_by, supersedes. */
  rel: string;
  ref: string;
}

/** KnowledgeNugget.json @ 0.1.0 */
export interface KnowledgeNugget {
  id: string;
  type: 'KnowledgeNugget';
  specVersion: string;
  sourceRef: NuggetSourceRef;
  warrant: NuggetWarrant;
  text: string;
  kkoTypeRefs?: string[];
  canonicalPayload?: unknown;
  provenance?: NuggetProvenanceLink[];
  policyLabels: string[];
  createdBy: string;
  wallTime: string;
  /** Non-negative integer, or an encoded vector/hybrid clock string. */
  logicalTime: number | string;
}

/**
 * A feed entry. A payload that will not parse is KEPT as `ok: false` with the reason, never
 * dropped and never coerced into a nugget with default fields.
 *
 * Why keep it at all: a silently discarded item makes the feed look cleaner than the data is.
 * The count of unreadable items is itself a signal, and the surface shows it.
 */
export type FeedItem =
  | { ok: true; nugget: KnowledgeNugget; nodeId: string }
  | { ok: false; nodeId: string; reason: string };

const WARRANT_TYPES: readonly NuggetWarrantType[] = [
  'direct-quote',
  'computed',
  'inferred',
  'model-generated',
];

export function isNuggetWarrantType(v: unknown): v is NuggetWarrantType {
  return typeof v === 'string' && (WARRANT_TYPES as readonly string[]).includes(v);
}

const str = (v: unknown): v is string => typeof v === 'string' && v.length > 0;
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/**
 * Parse one nugget, fail-closed.
 *
 * Every required field of the schema is checked. A nugget missing or mistyping ANY of them is
 * returned as unreadable with the field named — because the alternative (filling a default) is
 * how a `model-generated` nugget would eventually get read as something better.
 *
 * `warrant.type` is checked against the CLOSED v0.1 enum. An unrecognized value is unreadable,
 * not silently downgraded to a known member: inventing a type is how a contract bump upstream
 * turns into a wrong colour downstream.
 */
export function parseNugget(raw: unknown, nodeId = ''): FeedItem {
  const bad = (reason: string): FeedItem => ({ ok: false, nodeId, reason });
  if (!raw || typeof raw !== 'object') return bad('payload is not an object');
  const o = raw as Record<string, unknown>;

  if (!str(o['id'])) return bad('missing id');
  const id = o['id'];
  if (o['type'] !== 'KnowledgeNugget') return bad(`type is not KnowledgeNugget (got ${String(o['type'])})`);
  if (!str(o['specVersion'])) return bad('missing specVersion');
  if (!str(o['text'])) return bad('missing text');
  if (!str(o['createdBy'])) return bad('missing createdBy');
  if (!str(o['wallTime'])) return bad('missing wallTime');
  const logical = o['logicalTime'];
  if (!num(logical) && !str(logical)) return bad('missing logicalTime');

  const srcRaw = o['sourceRef'];
  if (!srcRaw || typeof srcRaw !== 'object') return bad('missing sourceRef');
  const src = srcRaw as Record<string, unknown>;
  const spanRaw = src['span'];
  if (!spanRaw || typeof spanRaw !== 'object') return bad('missing sourceRef.span');
  const sp = spanRaw as Record<string, unknown>;
  if (!num(sp['start']) || !num(sp['end'])) return bad('sourceRef.span offsets are not numbers');
  if (!str(src['docRef'])) return bad('missing sourceRef.docRef');
  if (!str(src['contentHash'])) return bad('missing sourceRef.contentHash');

  const wRaw = o['warrant'];
  if (!wRaw || typeof wRaw !== 'object') return bad('missing warrant');
  const w = wRaw as Record<string, unknown>;
  if (!isNuggetWarrantType(w['type'])) {
    return bad(`unrecognized warrant.type: ${String(w['type'])}`);
  }
  if (!num(w['confidence'])) return bad('missing warrant.confidence');
  const evidence = Array.isArray(w['evidence']) ? w['evidence'].filter(str) : [];
  // Schema invariant, re-checked here: a derivation that cites nothing is not a derivation.
  if ((w['type'] === 'computed' || w['type'] === 'inferred') && evidence.length === 0) {
    return bad(`${w['type']} warrant cites no evidence (schema requires >= 1)`);
  }

  const span: NuggetSpan = { start: sp['start'], end: sp['end'] };
  if (num(sp['page'])) span.page = sp['page'];

  const nugget: KnowledgeNugget = {
    id,
    type: 'KnowledgeNugget',
    specVersion: o['specVersion'],
    sourceRef: { docRef: src['docRef'], span, contentHash: src['contentHash'] },
    warrant: { type: w['type'], evidence, confidence: w['confidence'] },
    text: o['text'],
    kkoTypeRefs: Array.isArray(o['kkoTypeRefs']) ? o['kkoTypeRefs'].filter(str) : [],
    policyLabels: Array.isArray(o['policyLabels']) ? o['policyLabels'].filter(str) : [],
    createdBy: o['createdBy'],
    wallTime: o['wallTime'],
    logicalTime: logical,
  };
  if ('canonicalPayload' in o) nugget.canonicalPayload = o['canonicalPayload'];
  if (Array.isArray(o['provenance'])) {
    nugget.provenance = o['provenance']
      .filter((p): p is Record<string, unknown> => !!p && typeof p === 'object')
      .filter((p) => str(p['rel']) && str(p['ref']))
      .map((p) => ({ rel: p['rel'] as string, ref: p['ref'] as string }));
  }
  return { ok: true, nugget, nodeId: nodeId || id };
}

/**
 * The nugget's warrant, as the `<Warrant>` primitive's input.
 *
 * TWO decisions here are load-bearing:
 *
 * 1. `span` is supplied ONLY for `direct-quote`. `<Warrant>` renders `span` as "Source span" —
 *    the characters the claim points back at — and for a direct quote that is exactly true
 *    (the schema forces `end - start === text.length`). For computed / inferred /
 *    model-generated the span is the CONDITIONING WINDOW, and the schema says outright that it
 *    does not warrant the text. Passing it anyway would render an unwarranted claim as though
 *    it pointed at proof. The window is still shown on the card — labelled as what it is.
 *
 * 2. No `seal` and no `walk` are supplied, so every nugget resolves to `unknown`.
 *    KnowledgeNugget@0.1.0 has no receipt field: `apps/nugget-extractor`'s emitter seals the
 *    BATCH (one `POST /v1/compute kind=nugget-emit` receipt per document), not the nugget. So
 *    per-nugget seal state is genuinely unknown — which is not "unsealed", and is very much
 *    not "sealed". Fabricating a seal here is the exact failure #1052 closed.
 */
export function nuggetWarrantInput(n: KnowledgeNugget): WarrantInput {
  const input: WarrantInput = { claim: n.text, kind: n.warrant.type };
  if (n.warrant.type === 'direct-quote') {
    const span: TokenSpan = {
      start: n.sourceRef.span.start,
      end: n.sourceRef.span.end,
      text: n.text,
      tokenIndices: [],
    };
    input.span = span;
  }
  return input;
}

/** Short display form of a URN or URI: the last meaningful segment. */
export function refLabel(ref: string): string {
  const tail = ref.split(/[:/#]/).filter(Boolean).pop();
  return tail && tail.length > 0 ? tail : ref;
}
