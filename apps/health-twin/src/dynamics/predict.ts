// W10 — the twin's forward prediction: mechanistic base → learned residual proposal → reconciliation
// gate → SEALED RECEIPT. This is the only place the three halves meet, and the order is the doctrine:
//
//   1. physics runs FIRST and alone. mechanistic.ts integrates the organ compartments forward.
//   2. the surrogate proposes a DELTA per organ per step. It cannot express an absolute prediction.
//   3. the gate disposes. Admissible → accepted whole. Inadmissible → REJECTED with a typed reason,
//      the mechanistic value is emitted, and the refusal is recorded (never clamped, never silent).
//   4. the whole thing is sealed: which mechanistic model, which surrogate version and weight digest,
//      which gate policy, what it decided and why — bound into one sha256 snapshot.
//
// Non-diagnostic. This projects the trajectory of the person's own recorded numbers under the current
// regimen. It is not a diagnosis, not a prognosis, and not a medical device; a clinician decides.
import {
  simulate, anchorTo, observableOf, OBSERVABLE, SIGMA, DEFAULT_PARAMS, MODEL_ID, MODEL_VERSION,
  type Compartment, type MechanisticRun,
} from './mechanistic.js';
import { fitSurrogate, proposeDelta, SEED_COVARIATES, SURROGATE_ID, SURROGATE_VERSION } from './surrogate.js';
import {
  reconcile, recordRejections, auditEmission, gatePolicy, GATE_ID, GATE_POLICY_VERSION,
  ADMISSIBILITY_DIGEST, type GateDecision, type RejectionRecord, type RejectionReason,
} from './gate.js';
import { seal, verifySeal, q, type Seal } from './seal.js';
import { OBSERVATIONS } from '../data.js';

export const COMPARTMENTS: Compartment[] = ['cardio', 'hepatic', 'renal'];

/** Which body system each compartment's observable belongs to — so a prediction can be grant-scoped
 *  by the SAME consent membrane the record itself is (grants.ts), not by a second, weaker rule. */
export const COMPARTMENT_SYSTEM: Record<Compartment, string> = {
  cardio: OBSERVABLE.cardio.system, hepatic: OBSERVABLE.hepatic.system, renal: OBSERVABLE.renal.system,
};

export interface Covariates { adherencePdc: number; reninIndex: number; bmi: number; uacr: number }

export interface PredictOptions {
  horizonDays?: number;
  stepDays?: number;
  compartments?: Compartment[];
  /** Day-0 anchor. Defaults to the twin's own latest recorded observations. */
  observed?: { sbp?: number; a1c?: number; egfr?: number };
  covariates?: Covariates;
  /**
   * TEST-ONLY injection point: replace the surrogate's proposed delta. The proof harness uses it to
   * drive proposals across mechanistic bounds and check the gate refuses them. It is a function
   * argument only — it is never reachable from HTTP input, so no caller can steer the gate.
   */
  overrideDelta?: (k: Compartment, day: number, mechanistic: number) => number;
}

export interface OrganPrediction {
  compartment: Compartment;
  code: string; label: string; unit: string; organ: string; system: string;
  days: number[];
  /** The physics alone. */
  mechanistic: number[];
  /** What the surrogate wanted (mechanistic + delta), before adjudication. `null` where it emitted a
   *  non-finite value — recorded as null rather than invented as a number. */
  proposed: (number | null)[];
  /** What the twin emits: accepted proposals, mechanistic fallbacks where the gate refused. */
  emitted: number[];
  decisions: GateDecision[];
  accepted: number;
  rejected: number;
  byReason: Partial<Record<RejectionReason, number>>;
  /** The gate's own anti-clamp audit: every emitted value is the physics or the whole proposal. */
  emissionAudit: 'ok' | { violated: 'clamp'; law: string; violations: unknown[] };
  sigma: number;
}

export interface TwinPrediction {
  horizonDays: number;
  stepDays: number;
  anchoredTo: { sbp?: number; a1c?: number; egfr?: number };
  covariates: Covariates;
  organs: OrganPrediction[];
  gate: {
    policyVersion: string;
    admissibilityDigest: string;
    accepted: number;
    rejected: number;
    byReason: Partial<Record<RejectionReason, number>>;
    /** The refusals, in full — a rejection that is not visible may as well have been a clamp. */
    rejections: RejectionRecord[];
    doctrine: string;
  };
  provenance: {
    mechanistic: { model: string; version: string; params: string };
    surrogate: { id: string; version: string; coefficientsDigest: string; fittedOn: unknown; residualOnly: true };
    gate: { id: string; policyVersion: string; admissibilityDigest: string };
  };
  receipt: Seal;
  synthetic: true;
  disclaimer: string;
}

const DISCLAIMER =
  'Projection of this record’s own numbers under the current regimen, from a mechanistic organ model with a '
  + 'gated learned correction. Synthetic data. Not a diagnosis, not a prognosis, not a medical device — a clinician decides.';

/** The twin's latest recorded value for each compartment's observable. */
export function currentObservations(): { sbp?: number; a1c?: number; egfr?: number } {
  const byCode = (c: string) => OBSERVATIONS.find((o) => o.code === c)?.value;
  return { sbp: byCode(OBSERVABLE.cardio.code), a1c: byCode(OBSERVABLE.hepatic.code), egfr: byCode(OBSERVABLE.renal.code) };
}

function sampleDays(horizon: number, step: number): number[] {
  const days = [];
  for (let d = 0; d <= horizon; d += step) days.push(d);
  if (days[days.length - 1] !== horizon) days.push(horizon);
  return days;
}

/**
 * Run the twin forward and adjudicate every learned correction.
 * Deterministic: same inputs → same trajectory, same decisions, same seal.
 */
export function predict(opts: PredictOptions = {}): TwinPrediction {
  const horizonDays = Math.max(7, Math.min(365, Math.round(opts.horizonDays ?? 90)));
  const stepDays = Math.max(1, Math.min(30, Math.round(opts.stepDays ?? 7)));
  const compartments = (opts.compartments?.length ? opts.compartments : COMPARTMENTS).filter((k) => COMPARTMENTS.includes(k));
  const observed = { ...currentObservations(), ...(opts.observed ?? {}) };
  const covariates = opts.covariates ?? SEED_COVARIATES;

  const params = anchorTo(observed, DEFAULT_PARAMS);
  const run: MechanisticRun = simulate(horizonDays, params);
  const sur = fitSurrogate();
  const days = sampleDays(horizonDays, stepDays);

  const organs: OrganPrediction[] = [];
  const allDecisions: GateDecision[] = [];

  for (const k of compartments) {
    const mechanistic: number[] = [], proposed: (number | null)[] = [], emitted: number[] = [];
    const decisions: GateDecision[] = [];
    let previousEmitted = observableOf(run.steps[0]!, k);

    days.forEach((day, i) => {
      const step = run.steps[day]!;
      const mech = observableOf(step, k);
      if (i === 0) {
        // day 0 is the person's recorded state; there is nothing to correct yet
        mechanistic.push(q(mech)); proposed.push(q(mech)); emitted.push(q(mech));
        previousEmitted = mech;
        return;
      }
      const dayFrac = day / horizonDays;
      const delta = opts.overrideDelta
        ? opts.overrideDelta(k, day, mech)
        : proposeDelta(sur, k, covariates, dayFrac);
      const decision = reconcile({
        compartment: k, day, dtDays: day - days[i - 1]!,
        mechanistic: mech, previousEmitted, proposed: mech + delta, delta,
        step, params,
      });
      decisions.push(decision);
      mechanistic.push(q(mech));
      proposed.push(decision.proposed);
      emitted.push(decision.emitted);
      previousEmitted = decision.emitted;
    });

    const byReason: Partial<Record<RejectionReason, number>> = {};
    for (const d of decisions) if (d.verdict === 'rejected' && d.reason) byReason[d.reason] = (byReason[d.reason] ?? 0) + 1;
    const audit = auditEmission(decisions);

    organs.push({
      compartment: k, ...OBSERVABLE[k],
      days, mechanistic, proposed, emitted, decisions,
      accepted: decisions.filter((d) => d.verdict === 'accepted').length,
      rejected: decisions.filter((d) => d.verdict === 'rejected').length,
      byReason,
      emissionAudit: audit.ok ? 'ok' : { violated: 'clamp' as const, law: audit.law, violations: audit.violations },
      sigma: SIGMA[k],
    });
    allDecisions.push(...decisions);
  }

  const byReason: Partial<Record<RejectionReason, number>> = {};
  for (const d of allDecisions) if (d.verdict === 'rejected' && d.reason) byReason[d.reason] = (byReason[d.reason] ?? 0) + 1;

  // ── seal ───────────────────────────────────────────────────────────────────────────────────────
  // Inputs, output and provenance are digested separately and bound into one snapshot, so a surface
  // can prove after the fact WHICH model, WHICH surrogate weights and WHICH gate policy produced this.
  const inputs = { horizonDays, stepDays, compartments, observed, covariates };
  const output = organs.map((o) => ({
    compartment: o.compartment, days: o.days, mechanistic: o.mechanistic, emitted: o.emitted,
    decisions: o.decisions.map((d) => ({ day: d.day, verdict: d.verdict, reason: d.reason ?? null, proposed: d.proposed, emitted: d.emitted })),
  }));
  const provenance = {
    mechanistic: { model: MODEL_ID, version: MODEL_VERSION, params: digestParams(params) },
    surrogate: { id: SURROGATE_ID, version: SURROGATE_VERSION, coefficientsDigest: sur.coefficientsDigest, fittedOn: sur.fittedOn, residualOnly: true as const },
    gate: { id: GATE_ID, policyVersion: GATE_POLICY_VERSION, admissibilityDigest: ADMISSIBILITY_DIGEST },
  };
  const receipt = seal('prediction', inputs, output, provenance);
  const rejections = recordRejections(receipt.id, allDecisions);

  return {
    horizonDays, stepDays, anchoredTo: observed, covariates, organs,
    gate: {
      policyVersion: GATE_POLICY_VERSION, admissibilityDigest: ADMISSIBILITY_DIGEST,
      accepted: allDecisions.filter((d) => d.verdict === 'accepted').length,
      rejected: allDecisions.filter((d) => d.verdict === 'rejected').length,
      byReason, rejections,
      doctrine: gatePolicy().doctrine,
    },
    provenance, receipt, synthetic: true, disclaimer: DISCLAIMER,
  };
}

/** Content address of the mechanistic parameter set (the seal binds the params, not just the model id). */
function digestParams(p: unknown): string {
  // imported lazily to keep the seal helpers in one place
  return seal('params', p, null, null).inputsDigest;
}

/** Re-derive a prediction's seal from its own contents — the verification side of the receipt. */
export function verifyPrediction(p: TwinPrediction): boolean {
  const inputs = { horizonDays: p.horizonDays, stepDays: p.stepDays, compartments: p.organs.map((o) => o.compartment), observed: p.anchoredTo, covariates: p.covariates };
  const output = p.organs.map((o) => ({
    compartment: o.compartment, days: o.days, mechanistic: o.mechanistic, emitted: o.emitted,
    decisions: o.decisions.map((d) => ({ day: d.day, verdict: d.verdict, reason: d.reason ?? null, proposed: d.proposed, emitted: d.emitted })),
  }));
  return verifySeal(p.receipt, 'prediction', inputs, output, p.provenance);
}
