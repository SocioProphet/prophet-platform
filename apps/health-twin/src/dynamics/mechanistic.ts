// W10.1 — the MECHANISTIC BASE of the twin's dynamics. This is the "physics" half of "learned proposes,
// physics disposes": organ-level compartment models integrated forward in time, written from published
// pharmacokinetic / physiological structure, with NO fitted-to-our-data parameters. It is the base
// prediction; the learned surrogate (surrogate.ts) may only propose a RESIDUAL on top of it, and the
// reconciliation gate (gate.ts) decides whether that residual is physiologically admissible.
//
// Three compartments, chosen because the seed twin actually carries their observations and because each
// one contributes a DIFFERENT kind of mechanistic constraint the gate can enforce:
//
//   cardio   (SBP, LOINC 8480-6)   PK-PD: 1-compartment first-order PK for an ACE inhibitor driving an
//                                  Emax pharmacodynamic effect on systolic pressure. Gives a MASS-BALANCE
//                                  law (drug in = drug in body + cleared + never-absorbed) and a
//                                  MONOTONE dose-response (an ACE inhibitor cannot raise BP by its
//                                  mechanism, so the treated path never sits above the untreated path).
//   hepatic  (HbA1c, LOINC 4548-4) A lagged integrator of mean glucose over the red-cell pool. Gives a
//                                  genuine CONSERVATION bound: the glycated fraction of haemoglobin can
//                                  only change as fast as the pool turns over.
//   renal    (eGFR, LOINC 33914-3) First-order nephron loss accelerated by systolic pressure — coupled to
//                                  the cardio compartment, so this is a twin and not three scalars.
//                                  Gives an irreversibility/MONOTONICITY law: functioning nephron mass
//                                  does not regenerate on this horizon.
//
// Parameter provenance (population-typical values from the literature, NOT fitted here):
//   • lisinopril: oral bioavailability ~25%, effective t½ ~12 h, Vd ~124 L, tmax 6–8 h (→ ka ~0.5 /h).
//   • lisinopril 10 mg mean SBP reduction ~8–12 mmHg (Emax model asymptote set at the top of that band).
//   • HbA1c ↔ mean glucose: ADAG relation A1c(%) = (MG[mg/dL] + 46.7) / 28.7 (Nathan et al., 2008).
//   • HbA1c kinetics: exponential approach with τ ≈ 40 d (red-cell lifespan ~120 d; the ~50% of the A1c
//     value contributed by the most recent month is the standard clinical statement of the same lag).
//   • eGFR: age-related decline ~0.9 mL/min/1.73m²/yr after 40, accelerated by systolic hypertension.
//
// SYNTHETIC ONLY. This runs against the clearly-synthetic seed subject and the synthetic cohort in
// cohort.ts. It is NOT validated against real patients and is NOT a medical device. Non-diagnostic:
// it projects a trajectory of the person's own recorded numbers; a clinician decides anything.

export type Compartment = 'cardio' | 'hepatic' | 'renal';

/** The observable each compartment predicts, with the LOINC code it is measured by. */
export const OBSERVABLE: Record<Compartment, { code: string; label: string; unit: string; organ: string; system: string }> = {
  cardio: { code: '8480-6', label: 'Systolic blood pressure', unit: 'mmHg', organ: 'Heart', system: 'cardiovascular' },
  hepatic: { code: '4548-4', label: 'Hemoglobin A1c', unit: '%', organ: 'Pancreas', system: 'hepatic' },
  renal: { code: '33914-3', label: 'eGFR (kidney function)', unit: 'mL/min', organ: 'Kidneys', system: 'urinary' },
};

// ── parameters ───────────────────────────────────────────────────────────────────────────────────

/** Population-typical lisinopril PK-PD + baseline haemodynamics. */
export interface CardioParams {
  ka: number;      // 1/h   first-order absorption
  ke: number;      // 1/h   first-order elimination (ln2 / t½)
  F: number;       // —     oral bioavailability
  Vd: number;      // L     apparent volume of distribution
  doseMg: number;  // mg    per administration
  tauH: number;    // h     dosing interval
  Emax: number;    // mmHg  asymptotic SBP reduction
  EC50: number;    // mg/L  concentration at half-maximal effect
  sbp0: number;    // mmHg  untreated baseline systolic pressure
  driftPerDay: number; // mmHg/day untreated secular drift
}
export interface HepaticParams {
  tauA1cDays: number;  // d      time constant of the A1c lag (red-cell pool turnover)
  tauRbcDays: number;  // d      pool-replacement constant used by the conservation bound
  mg0: number;         // mg/dL  starting mean glucose
  mgTarget: number;    // mg/dL  mean glucose the current regimen drives toward
  tauMgDays: number;   // d      how fast mean glucose moves to target
  a1c0: number;        // %      starting A1c
}
export interface RenalParams {
  egfr0: number;          // mL/min/1.73m²
  agePerYear: number;     // mL/min per year, age-related nephron loss (positive = loss)
  bpSensitivity: number;  // mL/min per year per 10 mmHg above threshold
  bpThreshold: number;    // mmHg above which pressure accelerates loss
}
export interface MechanisticParams { cardio: CardioParams; hepatic: HepaticParams; renal: RenalParams }

export const MODEL_ID = 'organ-compartment-pkpd';
export const MODEL_VERSION = 'v1';

/** Population-typical defaults. Never fitted to our own data — that is the surrogate's job. */
export const DEFAULT_PARAMS: MechanisticParams = {
  cardio: {
    ka: 0.5, ke: Math.LN2 / 12, F: 0.25, Vd: 124, doseMg: 10, tauH: 24,
    Emax: 16, EC50: 0.005, sbp0: 145, driftPerDay: 0.006,
  },
  hepatic: {
    tauA1cDays: 40, tauRbcDays: 40, mg0: 123, mgTarget: 116, tauMgDays: 60, a1c0: 5.9,
  },
  renal: {
    egfr0: 92, agePerYear: 0.9, bpSensitivity: 0.35, bpThreshold: 120,
  },
};

// ── integrator ───────────────────────────────────────────────────────────────────────────────────

/** Classical RK4 on a vector field. Fixed step: the trajectory must be bit-reproducible for the seal. */
function rk4(y: number[], t: number, h: number, f: (t: number, y: number[]) => number[]): number[] {
  const add = (a: number[], b: number[], s: number) => a.map((v, i) => v + s * b[i]!);
  const k1 = f(t, y);
  const k2 = f(t + h / 2, add(y, k1, h / 2));
  const k3 = f(t + h / 2, add(y, k2, h / 2));
  const k4 = f(t + h, add(y, k3, h));
  return y.map((v, i) => v + (h / 6) * (k1[i]! + 2 * k2[i]! + 2 * k3[i]! + k4[i]!));
}

// ── the model ────────────────────────────────────────────────────────────────────────────────────

/** One day of the mechanistic trajectory: the observables plus the internal state the gate reasons over. */
export interface MechanisticStep {
  day: number;
  sbp: number;            // mmHg — treated systolic pressure
  sbpUntreated: number;   // mmHg — the same subject with no drug on board (the monotonicity reference)
  drugEffect: number;     // mmHg — the (non-negative) reduction the drug on board can produce
  concentration: number;  // mg/L — central-compartment concentration at the sampling instant
  a1c: number;            // %
  meanGlucose: number;    // mg/dL
  egfr: number;           // mL/min/1.73m²
  /** Drug mass balance at this instant, in mg. doseIn must equal gut + central + cleared + neverAbsorbed. */
  mass: { doseIn: number; gut: number; central: number; cleared: number; neverAbsorbed: number };
}

export interface MechanisticRun {
  model: string;          // MODEL_ID
  version: string;        // MODEL_VERSION
  horizonDays: number;
  steps: MechanisticStep[];
  params: MechanisticParams;
  /** Stated 1-σ uncertainty of the mechanistic prediction per compartment, in observable units.
   *  This is the band the gate uses to decide whether a learned correction is still a RESIDUAL.
   *  Sourced from the population spread of the underlying parameters, not from our own residuals. */
  sigma: Record<Compartment, number>;
}

/** Population 1-σ, in observable units. Wide enough to be honest, tight enough to bind the surrogate. */
export const SIGMA: Record<Compartment, number> = { cardio: 6.0, hepatic: 0.25, renal: 3.0 };

const STEPS_PER_HOUR = 4; // 15-minute PK step (ka = 0.5 /h makes intra-day peaks real)

/** Drug already on board at day 0: the subject has been taking it, this is not a first dose.
 *  30-day burn-in at the same regimen → the maintained steady state. */
export function steadyStateOnBoard(c: CardioParams): { gut: number; central: number } {
  const h = 1 / STEPS_PER_HOUR;
  let gut = 0, central = 0;
  for (let hh = 0; hh < 30 * 24 * STEPS_PER_HOUR; hh++) {
    const t = hh * h;
    if (Math.abs(t % c.tauH) < 1e-9) gut += c.doseMg;
    const st = rk4([gut, central], t, h, (_t, s) => [-c.ka * s[0]!, c.F * c.ka * s[0]! - c.ke * s[1]!]);
    gut = st[0]!; central = st[1]!;
  }
  return { gut, central };
}

/** Emax pharmacodynamics: the SBP reduction (mmHg, non-negative) a concentration can produce. */
export const emaxEffect = (c: CardioParams, conc: number) => (c.Emax * conc) / (c.EC50 + conc);

/**
 * A TWIN is initialised from the PERSON, not from a textbook average: re-anchor the baseline terms so
 * the day-0 prediction reproduces the subject's own latest recorded observations. For SBP the anchor is
 * on the UNTREATED baseline (observed = untreated − drug effect on board), so the drug's contribution
 * stays mechanistic rather than being absorbed into the intercept.
 */
export function anchorTo(observed: { sbp?: number; a1c?: number; egfr?: number }, base: MechanisticParams = DEFAULT_PARAMS): MechanisticParams {
  const ss = steadyStateOnBoard(base.cardio);
  const effect0 = emaxEffect(base.cardio, ss.central / base.cardio.Vd);
  return {
    cardio: { ...base.cardio, sbp0: observed.sbp != null ? observed.sbp + effect0 : base.cardio.sbp0 },
    hepatic: { ...base.hepatic, a1c0: observed.a1c ?? base.hepatic.a1c0 },
    renal: { ...base.renal, egfr0: observed.egfr ?? base.renal.egfr0 },
  };
}

/**
 * Integrate the mechanistic twin forward `horizonDays` from the subject's current state.
 *
 * PK is resolved at 15-minute resolution; the observables are sampled once per day at the trough — the
 * instant a clinic actually measures a trough BP. Renal is driven by the cardio compartment's daily
 * systolic pressure, so the compartments are coupled.
 */
export function simulate(horizonDays: number, p: MechanisticParams = DEFAULT_PARAMS): MechanisticRun {
  const c = p.cardio, hp = p.hepatic, r = p.renal;
  const stepsPerHour = STEPS_PER_HOUR;
  const h = 1 / stepsPerHour;             // hours
  const totalHours = horizonDays * 24;

  // PK state: [gut, central] in mg. Plus accumulators for the mass balance.
  const ss = steadyStateOnBoard(c);
  let y = [ss.gut, ss.central];
  let cleared = 0, neverAbsorbed = 0;
  // Open the mass ledger at the on-board mass: we account from t=0 forward, so the drug already in the
  // body IS the opening balance. doseIn − (gut + central + cleared + neverAbsorbed) must stay 0 from here.
  let doseIn = ss.gut + ss.central;

  const steps: MechanisticStep[] = [];
  let a1c = hp.a1c0;
  let egfr = r.egfr0;

  const untreatedAt = (day: number) => c.sbp0 + c.driftPerDay * day;
  const effectOf = (conc: number) => emaxEffect(c, conc);
  const meanGlucoseAt = (day: number) => hp.mgTarget + (hp.mg0 - hp.mgTarget) * Math.exp(-day / hp.tauMgDays);
  const a1cEqAt = (day: number) => (meanGlucoseAt(day) + 46.7) / 28.7;

  // day 0 sample (the state as it stands now)
  const push = (day: number) => {
    const conc = y[1]! / c.Vd;
    const drugEffect = effectOf(conc);
    const sbpUntreated = untreatedAt(day);
    steps.push({
      day,
      sbp: sbpUntreated - drugEffect,
      sbpUntreated, drugEffect, concentration: conc,
      a1c, meanGlucose: meanGlucoseAt(day), egfr,
      mass: { doseIn, gut: y[0]!, central: y[1]!, cleared, neverAbsorbed },
    });
  };
  push(0);

  for (let hh = 0; hh < totalHours * stepsPerHour; hh++) {
    const t = hh * h;
    if (Math.abs(t % c.tauH) < 1e-9) { y[0]! += c.doseMg; doseIn += c.doseMg; }
    const before = y.slice();
    y = rk4(y, t, h, (_t, s) => [-c.ka * s[0]!, c.F * c.ka * s[0]! - c.ke * s[1]!]);
    // account the mass that left the gut: F of it reached the central compartment, (1-F) never absorbed
    const leftGut = before[0]! - y[0]!;
    neverAbsorbed += (1 - c.F) * leftGut;
    // account elimination as the balance of the central compartment
    cleared += c.F * leftGut - (y[1]! - before[1]!);

    // once per day, advance the slow compartments and sample
    if (Math.abs(((hh + 1) * h) % 24) < 1e-9) {
      const day = Math.round(((hh + 1) * h) / 24);
      // A1c: first-order approach to the ADAG equilibrium for the current mean glucose
      a1c = rk4([a1c], day - 1, 1, (tt, s) => [(a1cEqAt(tt) - s[0]!) / hp.tauA1cDays])[0]!;
      // eGFR: age-related loss accelerated by the systolic pressure the cardio compartment just produced
      const sbpToday = untreatedAt(day) - effectOf(y[1]! / c.Vd);
      const excess = Math.max(0, sbpToday - r.bpThreshold) / 10;
      egfr -= (r.agePerYear + r.bpSensitivity * excess) / 365;
      push(day);
    }
  }

  return { model: MODEL_ID, version: MODEL_VERSION, horizonDays, steps, params: p, sigma: SIGMA };
}

/** Read the observable a compartment predicts out of a step. */
export function observableOf(step: MechanisticStep, k: Compartment): number {
  return k === 'cardio' ? step.sbp : k === 'hepatic' ? step.a1c : step.egfr;
}

/** Drug mass balance residual, in mg. Must be ~0 at every step or the integrator itself is wrong. */
export function massImbalance(step: MechanisticStep): number {
  const m = step.mass;
  return Math.abs(m.doseIn - (m.gut + m.central + m.cleared + m.neverAbsorbed));
}
