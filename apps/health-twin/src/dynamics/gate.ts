// W10.2 — THE RECONCILIATION GATE. "Learned proposes, physics disposes."
//
// This is the thing that separates a stored state model from a predictive twin. The surrogate may
// propose a correction to the mechanistic prediction at every step; this gate decides, step by step,
// whether that correction is PHYSIOLOGICALLY ADMISSIBLE. If it is, it is accepted whole. If it violates
// a mechanistic constraint it is REJECTED with a TYPED REASON, the twin falls back to the physics, and
// the rejection is RECORDED.
//
// 🔴 THE GATE NEVER CLAMPS. This is the load-bearing rule and it is deliberate. Clamping an inadmissible
// proposal to the nearest legal value would emit a number that is (a) not the physics, (b) not what the
// model proposed, and (c) indistinguishable at the surface from an accepted prediction. That is the
// silent-wrong class this estate keeps finding: the failure is hidden inside a plausible-looking output.
// So on rejection the emitted value is EXACTLY the mechanistic value — never the boundary — and the
// proposal, the rule it broke, the bound and the observed magnitude all survive into the ledger, the
// response and the seal. A caller can always tell the difference between "the physics said 138" and
// "the learned model wanted 191 and was refused".
//
// The rules below are per-organ because the laws are per-organ. Each rule names the mechanism it
// enforces, so a rejection is explainable to a clinician in one sentence, not just a code.
import {
  OBSERVABLE, SIGMA, type Compartment, type MechanisticStep, type MechanisticParams,
} from './mechanistic.js';
import { canonical, digest, q } from './seal.js';

export const GATE_ID = 'reconciliation-gate';
export const GATE_POLICY_VERSION = 'v1';

/** Every way a proposal can be refused. A rejection is always one of these — never a bare string. */
export type RejectionReason =
  | 'nonfinite'      // the proposal is NaN or ±Infinity
  | 'range'          // outside the hard physiological range of the observable
  | 'conservation'   // violates a mass-balance law (haemoglobin pool; trajectory accounting)
  | 'monotonicity'   // moves in a direction the mechanism cannot produce
  | 'rate'           // moves faster than physiology permits over the step
  | 'envelope';      // larger than the mechanism's own uncertainty — a replacement, not a residual

export const REJECTION_REASONS: RejectionReason[] = ['nonfinite', 'range', 'conservation', 'monotonicity', 'rate', 'envelope'];

// ── the admissibility constants ──────────────────────────────────────────────────────────────────

/** Hard physiological range of each observable. Outside this the number is not a body state at all. */
export const RANGE: Record<Compartment, { lo: number; hi: number }> = {
  cardio: { lo: 60, hi: 260 },     // mmHg systolic — measurable/survivable band
  hepatic: { lo: 3.5, hi: 20 },    // % HbA1c
  renal: { lo: 3, hi: 150 },       // mL/min/1.73m²
};

/** Maximum plausible change per day for a CHRONIC trajectory (this model does not predict crises). */
export const MAX_RATE_PER_DAY: Record<Compartment, number> = {
  cardio: 12,      // mmHg/day
  hepatic: 0.05,   // %/day
  renal: 1.0,      // mL/min/day
};

/** How far a residual may move the answer, in multiples of the mechanistic model's own 1-σ.
 *  Above this the learned term has stopped correcting the physics and started replacing it. */
export const ENVELOPE_K = 2.0;

/** Tolerances that absorb assay noise and float error so a rule fires on physics, not on rounding. */
const TOL = { cardio: 0.5, hepatic: 0.02, renal: 0.3 } as Record<Compartment, number>;

// ── rule declarations (documentation the gate itself emits, so the policy is inspectable) ────────

export interface AdmissibilityRule {
  reason: RejectionReason;
  compartments: Compartment[];
  /** The mechanism being enforced, in one sentence a clinician can read. */
  law: string;
  /** The numeric bound, as an expression. */
  bound: string;
}

export const RULES: AdmissibilityRule[] = [
  { reason: 'nonfinite', compartments: ['cardio', 'hepatic', 'renal'],
    law: 'A body state is a real number; NaN or infinity is not a prediction.',
    bound: 'Number.isFinite(proposed)' },
  { reason: 'range', compartments: ['cardio', 'hepatic', 'renal'],
    law: 'The observable must lie inside the hard physiological range for that measurement.',
    bound: `SBP ∈ [${RANGE.cardio.lo}, ${RANGE.cardio.hi}] mmHg · A1c ∈ [${RANGE.hepatic.lo}, ${RANGE.hepatic.hi}] % · eGFR ∈ [${RANGE.renal.lo}, ${RANGE.renal.hi}] mL/min` },
  { reason: 'conservation', compartments: ['hepatic'],
    law: 'Haemoglobin-pool mass balance: HbA1c is the glycated fraction of a red-cell pool that turns over with a ~40-day constant, so it cannot move faster than the pool can be replaced.',
    bound: '|ΔA1c| ≤ (Δt / τ_rbc) · max(A1c_max − A1c, A1c − A1c_min)' },
  { reason: 'monotonicity', compartments: ['cardio'],
    law: 'An ACE inhibitor cannot raise blood pressure through its own mechanism, so the treated trajectory never sits above the untreated baseline trajectory.',
    bound: 'proposed ≤ sbpUntreated(t) + tol' },
  { reason: 'monotonicity', compartments: ['renal'],
    law: 'Functioning nephron mass does not regenerate on this horizon, so eGFR is non-increasing under the model.',
    bound: 'proposed ≤ previousAccepted + tol' },
  { reason: 'rate', compartments: ['cardio', 'hepatic', 'renal'],
    law: 'The observable cannot move faster over a step than a chronic trajectory permits.',
    bound: `|Δ|/Δt ≤ ${MAX_RATE_PER_DAY.cardio} mmHg/d · ${MAX_RATE_PER_DAY.hepatic} %/d · ${MAX_RATE_PER_DAY.renal} mL/min/d` },
  { reason: 'envelope', compartments: ['cardio', 'hepatic', 'renal'],
    law: 'The learned term is a RESIDUAL, not a replacement: a correction larger than the mechanistic model\'s own uncertainty is a competing prediction and must not ride in as a correction.',
    bound: `|delta| ≤ ${ENVELOPE_K}σ  (σ = ${SIGMA.cardio} mmHg · ${SIGMA.hepatic} % · ${SIGMA.renal} mL/min)` },
];

/** Content address of the policy: the seal binds this, so a changed rule changes every future seal. */
export const ADMISSIBILITY_DIGEST = digest(canonical({ RULES, RANGE, MAX_RATE_PER_DAY, ENVELOPE_K, TOL, version: GATE_POLICY_VERSION }));

// ── adjudication ─────────────────────────────────────────────────────────────────────────────────

export interface GateContext {
  compartment: Compartment;
  day: number;
  dtDays: number;
  /** The physics base for this step — what is emitted if the proposal is refused. */
  mechanistic: number;
  /** The last value the twin actually emitted (accepted or mechanistic fallback). */
  previousEmitted: number;
  /** The surrogate's proposal = mechanistic + delta. */
  proposed: number;
  delta: number;
  /** Full mechanistic state at this step (untreated path, drug on board, …). */
  step: MechanisticStep;
  params: MechanisticParams;
}

export interface GateDecision {
  compartment: Compartment;
  day: number;
  verdict: 'accepted' | 'rejected';
  /** The physics base. */
  mechanistic: number;
  /** What the surrogate wanted. `null` when the surrogate emitted a non-finite value — recorded as
   *  null rather than coerced to a number, because a fabricated number here would itself be a lie. */
  proposed: number | null;
  delta: number | null;
  /** What the surrogate literally emitted when it was not a finite number ('NaN' / 'Infinity' / …). */
  nonFinite?: string;
  /** What the twin actually emits. On a rejection this is EXACTLY `mechanistic` — never a clamp. */
  emitted: number;
  reason?: RejectionReason;
  law?: string;
  bound?: string;
  /** The measured violation, so the rejection is auditable and not just labelled. */
  measured?: { got: number | null; limit: number | null; units: string };
  /** Explicit, machine-checkable statement of the no-clamp rule for this decision. */
  clamped: false;
}

type Violation = { reason: RejectionReason; law: string; bound: string; got: number | null; limit: number | null } | null;

const ruleFor = (reason: RejectionReason, k: Compartment) =>
  RULES.find((r) => r.reason === reason && r.compartments.includes(k))!;

/**
 * Adjudicate one proposal. Rules are evaluated in escalating order of specificity so the reported
 * reason is the most fundamental law broken: a NaN is reported as `nonfinite`, not as `range`.
 */
function adjudicate(ctx: GateContext): Violation {
  const k = ctx.compartment;
  const tol = TOL[k];

  // 1. nonfinite — a body state is a real number
  if (!Number.isFinite(ctx.proposed) || !Number.isFinite(ctx.delta)) {
    const r = ruleFor('nonfinite', k);
    return { reason: 'nonfinite', law: r.law, bound: r.bound, got: null, limit: null };
  }

  // 2. range — hard physiological limits of the observable
  const rng = RANGE[k];
  if (ctx.proposed < rng.lo || ctx.proposed > rng.hi) {
    const r = ruleFor('range', k);
    return { reason: 'range', law: r.law, bound: r.bound, got: ctx.proposed, limit: ctx.proposed < rng.lo ? rng.lo : rng.hi };
  }

  // 3. conservation — haemoglobin-pool mass balance (hepatic only; see the note below for cardio)
  if (k === 'hepatic') {
    const tau = ctx.params.hepatic.tauRbcDays;
    const drive = Math.max(RANGE.hepatic.hi - ctx.previousEmitted, ctx.previousEmitted - RANGE.hepatic.lo);
    const maxMove = (ctx.dtDays / tau) * drive + tol;
    const move = Math.abs(ctx.proposed - ctx.previousEmitted);
    if (move > maxMove) {
      const r = ruleFor('conservation', 'hepatic');
      return { reason: 'conservation', law: r.law, bound: r.bound, got: move, limit: maxMove };
    }
  }
  // NOTE — cardio deliberately has NO conservation rule. The drug mass balance
  // (doseIn = gut + central + cleared + neverAbsorbed) genuinely holds, and it IS enforced, but on the
  // mechanistic integrator itself, not on the residual: the residual is unattributed, so it is not a
  // claim about the drug compartment and the mass balance does not constrain it. Inventing a cardio
  // "conservation" rule to make the table look symmetric would be a fake law.

  // 4. monotonicity — directions the mechanism cannot produce
  if (k === 'cardio' && ctx.proposed > ctx.step.sbpUntreated + tol) {
    const r = ruleFor('monotonicity', 'cardio');
    return { reason: 'monotonicity', law: r.law, bound: r.bound, got: ctx.proposed, limit: ctx.step.sbpUntreated + tol };
  }
  if (k === 'renal' && ctx.proposed > ctx.previousEmitted + tol) {
    const r = ruleFor('monotonicity', 'renal');
    return { reason: 'monotonicity', law: r.law, bound: r.bound, got: ctx.proposed, limit: ctx.previousEmitted + tol };
  }

  // 5. rate — chronic-trajectory slew limit
  const rate = Math.abs(ctx.proposed - ctx.previousEmitted) / Math.max(ctx.dtDays, 1e-9);
  if (rate > MAX_RATE_PER_DAY[k]) {
    const r = ruleFor('rate', k);
    return { reason: 'rate', law: r.law, bound: r.bound, got: rate, limit: MAX_RATE_PER_DAY[k] };
  }

  // 6. envelope — a residual may not exceed the mechanism's own uncertainty
  const cap = ENVELOPE_K * SIGMA[k];
  if (Math.abs(ctx.delta) > cap) {
    const r = ruleFor('envelope', k);
    return { reason: 'envelope', law: r.law, bound: r.bound, got: Math.abs(ctx.delta), limit: cap };
  }

  return null;
}

/**
 * The gate. Accepts the proposal whole, or refuses it whole and falls back to the physics.
 * There is no third outcome and, in particular, no clamp.
 */
export function reconcile(ctx: GateContext): GateDecision {
  const v = adjudicate(ctx);
  const units = OBSERVABLE[ctx.compartment].unit;
  const finite = Number.isFinite(ctx.proposed) && Number.isFinite(ctx.delta);
  const base = {
    compartment: ctx.compartment, day: ctx.day,
    mechanistic: q(ctx.mechanistic),
    proposed: finite ? q(ctx.proposed) : null,
    delta: finite ? q(ctx.delta) : null,
    ...(finite ? {} : { nonFinite: String(ctx.proposed) }),
    clamped: false as const,
  };
  if (!v) return { ...base, verdict: 'accepted', emitted: q(ctx.proposed) };
  return {
    ...base, verdict: 'rejected',
    // physics disposes: the emitted value is the mechanistic one, NOT the boundary the proposal broke
    emitted: q(ctx.mechanistic),
    reason: v.reason, law: v.law, bound: v.bound,
    measured: { got: v.got == null ? null : q(v.got, 4), limit: v.limit == null ? null : q(v.limit, 4), units },
  };
}

// ── the gate's self-audit: the anti-clamp law ────────────────────────────────────────────────────
//
// This is NOT an admissibility rule (it does not judge the surrogate) — it audits the GATE ITSELF after
// assembly, and it is the check that makes "never clamps" a property rather than a comment.
//
// The law: EVERY emitted value is either the mechanistic base (the proposal was refused) or the
// proposal in full (it was accepted). There is no admissible third value. Any emitted number strictly
// between the two is, by definition, a partially-applied correction — which is exactly the silent
// clamp: a plausible-looking output that is neither the physics nor the model, and that no downstream
// reader can distinguish from an honest one.

export const EMISSION_LAW =
  'Every emitted value is either the mechanistic base (proposal refused) or the proposal in full (accepted). '
  + 'An intermediate value is a hidden clamp and is not permitted.';

export interface EmissionViolation { compartment: Compartment; day: number; emitted: number; mechanistic: number; proposed: number | null }

/** Audit a set of decisions against the anti-clamp law. Returns every violation, not just the first. */
export function auditEmission(decisions: GateDecision[]): { ok: true } | { ok: false; law: string; violations: EmissionViolation[] } {
  const violations: EmissionViolation[] = [];
  for (const d of decisions) {
    const legal = d.verdict === 'accepted' ? d.proposed : d.mechanistic;
    if (legal === null || d.emitted !== legal) {
      violations.push({ compartment: d.compartment, day: d.day, emitted: d.emitted, mechanistic: d.mechanistic, proposed: d.proposed });
    }
  }
  return violations.length === 0 ? { ok: true } : { ok: false, law: EMISSION_LAW, violations };
}

// ── the rejection ledger ─────────────────────────────────────────────────────────────────────────
//
// A rejection that is not recorded may as well have been a clamp. Every refusal lands here, keyed to
// the sealed prediction it belongs to, and the server exposes it. Local-first, in-memory in this
// skeleton — the same store discipline as the grant ledger.

export interface RejectionRecord extends GateDecision {
  verdict: 'rejected';
  predictionId: string;
  at: string;
}

const LEDGER: RejectionRecord[] = [];
const LEDGER_CAP = 500;

export function recordRejections(predictionId: string, decisions: GateDecision[]): RejectionRecord[] {
  const at = new Date().toISOString();
  const recs = decisions
    .filter((d): d is GateDecision & { verdict: 'rejected' } => d.verdict === 'rejected')
    .map((d) => ({ ...d, predictionId, at }));
  LEDGER.unshift(...recs);
  if (LEDGER.length > LEDGER_CAP) LEDGER.length = LEDGER_CAP;
  return recs;
}

export function rejectionLedger(limit = 100): { count: number; rejections: RejectionRecord[]; byReason: Record<string, number> } {
  const byReason: Record<string, number> = {};
  for (const r of LEDGER) byReason[r.reason!] = (byReason[r.reason!] ?? 0) + 1;
  return { count: LEDGER.length, rejections: LEDGER.slice(0, limit), byReason };
}

/** Test-only: reset the ledger between harness scenarios. */
export function _clearLedger(): void { LEDGER.length = 0; }

// ── the canonical reconciliation verdict ─────────────────────────────────────────────────────────
//
// This vocabulary is NOT invented here. `human-digital-twin`'s body-state model schema
// (`api/schemas/body-state/body-state-model.schema.json`, `dynamical_model.reconciliation`) already
// declares it, together with the phrase this whole wave is named after — "learned proposes, physics
// disposes: 'learned_only'/'divergent' MUST NOT drive human actuation." The schema had the contract and
// no executable model to satisfy it; this is the executable half, so it speaks the schema's words.
//
// The schema also carries the safety invariant as a JSON-Schema `allOf`: a state reconciled as
// `learned_only` or `divergent` must have omega_state ≤ TRUSTED and human_actuation blocked. We emit
// that consequence with the verdict, rather than leaving a downstream reader to look it up.

export type ReconciliationVerdict = 'physics_verified' | 'physics_adjusted' | 'learned_only' | 'divergent' | 'not_run';

export interface Reconciliation {
  verdict: ReconciliationVerdict;
  schema: string;
  /** sourceos ExecutionDecision (allow|deny|ask|defer|rewrite). Fail-closed on divergence. */
  executionDecision: 'allow' | 'deny';
  /** The schema's own safety consequence, made explicit rather than left to be looked up. */
  humanActuation: 'permitted' | 'blocked';
  omegaCeiling: 'TRUSTED' | null;
  reason: string;
}

/**
 * Classify a whole run.
 *   not_run           nothing was adjudicated
 *   physics_verified  every proposal was admissible and none of them moved the answer — the physics stands
 *   physics_adjusted  corrections were accepted and applied, with no refusals
 *   divergent         at least one proposal was REFUSED — the learned model went somewhere physics
 *                     would not follow, which is the signal that must gate actuation
 *   learned_only      unreachable here BY CONSTRUCTION: this engine always integrates the mechanistic
 *                     model first and the surrogate cannot express an absolute value, so there is no
 *                     path that emits a learned-only state. Kept in the type to match the schema.
 */
export function reconciliationVerdict(decisions: GateDecision[]): Reconciliation {
  const schema = 'human-digital-twin body-state-model.schema.json#/dynamical_model/reconciliation';
  if (decisions.length === 0) {
    return { verdict: 'not_run', schema, executionDecision: 'allow', humanActuation: 'permitted', omegaCeiling: null,
      reason: 'no forward step was adjudicated' };
  }
  const rejected = decisions.filter((d) => d.verdict === 'rejected').length;
  if (rejected > 0) {
    return {
      verdict: 'divergent', schema, executionDecision: 'deny', humanActuation: 'blocked', omegaCeiling: 'TRUSTED',
      reason: `${rejected} of ${decisions.length} learned proposals were refused as physiologically inadmissible. `
        + 'Per the body-state schema safety invariant, a divergent forward model must not drive human actuation '
        + 'and cannot be promoted past TRUSTED. The emitted trajectory is the mechanistic one; it is still readable.',
    };
  }
  const moved = decisions.some((d) => d.emitted !== d.mechanistic);
  return moved
    ? { verdict: 'physics_adjusted', schema, executionDecision: 'allow', humanActuation: 'permitted', omegaCeiling: null,
        reason: `all ${decisions.length} learned corrections were physiologically admissible and were applied on top of the mechanistic base` }
    : { verdict: 'physics_verified', schema, executionDecision: 'allow', humanActuation: 'permitted', omegaCeiling: null,
        reason: 'the learned model proposed nothing that moved the answer; the mechanistic trajectory stands unchanged' };
}

/** The policy, as data — so a surface can show WHY something was refused without hard-coding the rules. */
export function gatePolicy() {
  return {
    gate: GATE_ID, policyVersion: GATE_POLICY_VERSION, admissibilityDigest: ADMISSIBILITY_DIGEST,
    reasons: REJECTION_REASONS, rules: RULES, range: RANGE, maxRatePerDay: MAX_RATE_PER_DAY,
    envelopeK: ENVELOPE_K, sigma: SIGMA, emissionLaw: EMISSION_LAW,
    doctrine: 'Learned proposes, physics disposes. An inadmissible proposal is REJECTED with a typed reason and the mechanistic value is emitted in its place — never a clamp, and never silently.',
  };
}
