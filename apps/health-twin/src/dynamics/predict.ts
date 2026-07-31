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
  reconcile, recordRejections, auditEmission, gatePolicy, reconciliationVerdict, GATE_ID, GATE_POLICY_VERSION,
  ADMISSIBILITY_DIGEST, EMISSION_LAW,
  type GateDecision, type RejectionRecord, type RejectionReason, type Reconciliation,
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
  /**
   * TEST-ONLY injection point, same discipline as `overrideDelta`: rewrite a compartment's decisions
   * AFTER adjudication, so the harness can simulate a BROKEN GATE — one that clamps. There is no other
   * way to exercise the anti-clamp response: `reconcile()` cannot produce a clamp, which is the point,
   * so a gate that clamps has to be forged to prove the audit acts on it. Function argument only, never
   * read from HTTP input.
   */
  overrideDecisions?: (k: Compartment, decisions: GateDecision[]) => GateDecision[];
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
  /** This organ's verdict in the body-state schema's own vocabulary. */
  reconciliation: Reconciliation;
  sigma: number;
}

export interface TwinPrediction {
  horizonDays: number;
  stepDays: number;
  anchoredTo: { sbp?: number; a1c?: number; egfr?: number };
  covariates: Covariates;
  organs: OrganPrediction[];
  /** The whole run's verdict, in the vocabulary the body-state schema already declares. */
  reconciliation: Reconciliation;
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

// ── the sealed projection ────────────────────────────────────────────────────────────────────────
//
// 🔴 ONE function, called by both `predict()` (which computes the seal) and `verifyPrediction()`
// (which re-derives it). It used to be written out twice, by hand, and the two copies had already
// drifted: neither included `emissionAudit`, so a clamp violation did not perturb the digest and was
// UNPROVABLE from the receipt afterwards — the receipt said "this run is fine" whether or not it was.
// A seal that omits the audit of its own emission is a seal over the part nobody doubts.
//
// What the projection must therefore bind, and why each is load-bearing:
//   • emitted / mechanistic / decisions — the numbers and the adjudication that produced them;
//   • emissionAudit — the ANTI-CLAMP verdict. Without it a clamped run and an honest run seal alike;
//   • reconciliation (per organ AND for the run) — the safety verdict the request path acts on. It is
//     derivable from the decisions today, but "derivable" is not "bound": a future change to
//     reconciliationVerdict() could flip deny→allow without moving a single digest.
function sealedProjection(organs: OrganPrediction[], reconciliation: Reconciliation) {
  return {
    reconciliation,
    organs: organs.map((o) => ({
      compartment: o.compartment, days: o.days, mechanistic: o.mechanistic, emitted: o.emitted,
      decisions: o.decisions.map((d) => ({ day: d.day, verdict: d.verdict, reason: d.reason ?? null, proposed: d.proposed, emitted: d.emitted })),
      emissionAudit: o.emissionAudit,
      reconciliation: o.reconciliation,
    })),
  };
}

/**
 * Raised when the gate's own anti-clamp audit fails — i.e. the engine emitted a value that is neither
 * the physics nor the whole proposal. This is NOT a caller error and it is not a rejected proposal: it
 * means the GATE ITSELF is broken, and the number it produced is the silent-wrong class in the flesh.
 *
 * The audit result used to only choose which literal to write into a field nobody read. Now it fails
 * CLOSED: the prediction is sealed first (so the violation is bound into a receipt and provable after
 * the fact) and then refused, so a clamped clinical number never reaches a caller at all.
 */
export class EmissionLawViolation extends Error {
  readonly name = 'EmissionLawViolation';
  constructor(
    readonly law: string,
    readonly violations: { compartment: Compartment; violations: unknown[] }[],
    readonly receipt: Seal,
  ) {
    super(`the gate emitted a value that is neither the physics nor the whole proposal (${violations.map((v) => v.compartment).join(', ')}) — refusing to serve a clamped prediction; receipt ${receipt.id}`);
  }
}

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
    const mechanistic: number[] = [], proposed: (number | null)[] = [];
    let emitted: number[] = [];
    let decisions: GateDecision[] = [];
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

    // TEST-ONLY: simulate a gate that clamps, so the anti-clamp response can be proven to have teeth.
    // The emitted trajectory is re-read from the (possibly rewritten) decisions, because a forged clamp
    // that did not move `emitted` would not be a clamp — it would be a mislabelled record.
    if (opts.overrideDecisions) {
      decisions = opts.overrideDecisions(k, decisions);
      emitted = [emitted[0]!, ...decisions.map((d) => d.emitted)];
    }

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
      reconciliation: reconciliationVerdict(decisions),
      sigma: SIGMA[k],
    });
    allDecisions.push(...decisions);
  }

  const byReason: Partial<Record<RejectionReason, number>> = {};
  for (const d of allDecisions) if (d.verdict === 'rejected' && d.reason) byReason[d.reason] = (byReason[d.reason] ?? 0) + 1;

  const reconciliation = reconciliationVerdict(allDecisions);

  // ── seal ───────────────────────────────────────────────────────────────────────────────────────
  // Inputs, output and provenance are digested separately and bound into one snapshot, so a surface
  // can prove after the fact WHICH model, WHICH surrogate weights and WHICH gate policy produced this.
  const inputs = { horizonDays, stepDays, compartments, observed, covariates };
  const output = sealedProjection(organs, reconciliation);
  const provenance = {
    mechanistic: { model: MODEL_ID, version: MODEL_VERSION, params: digestParams(params) },
    surrogate: { id: SURROGATE_ID, version: SURROGATE_VERSION, coefficientsDigest: sur.coefficientsDigest, fittedOn: sur.fittedOn, residualOnly: true as const },
    gate: { id: GATE_ID, policyVersion: GATE_POLICY_VERSION, admissibilityDigest: ADMISSIBILITY_DIGEST },
  };
  const receipt = seal('prediction', inputs, output, provenance);
  const rejections = recordRejections(receipt.id, allDecisions);

  // ── the anti-clamp law, ENFORCED ───────────────────────────────────────────────────────────────
  // Sealed FIRST, refused SECOND, and the order is the whole point: the receipt exists and binds the
  // violation, so the failure is provable after the fact — and then nothing is served. A clamped value
  // that is merely LABELLED as clamped is still a clamped clinical number on a surface.
  const clamped = organs
    .filter((o) => o.emissionAudit !== 'ok')
    .map((o) => ({ compartment: o.compartment, violations: (o.emissionAudit as { violations: unknown[] }).violations }));
  if (clamped.length > 0) throw new EmissionLawViolation(EMISSION_LAW, clamped, receipt);

  return {
    horizonDays, stepDays, anchoredTo: observed, covariates, organs,
    reconciliation,
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

/**
 * Re-derive a prediction's seal from its own contents — the verification side of the receipt.
 * Uses the SAME `sealedProjection` the seal was computed over, so the two can no longer drift apart.
 */
export function verifyPrediction(p: TwinPrediction): boolean {
  const inputs = { horizonDays: p.horizonDays, stepDays: p.stepDays, compartments: p.organs.map((o) => o.compartment), observed: p.anchoredTo, covariates: p.covariates };
  const output = sealedProjection(p.organs, p.reconciliation);
  return verifySeal(p.receipt, 'prediction', inputs, output, p.provenance);
}
