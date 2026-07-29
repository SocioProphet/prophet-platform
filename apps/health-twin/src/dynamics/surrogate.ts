// W10.1 — THE LEARNED SURROGATE, as an organ-level RESIDUAL model.
//
// The rule that makes this a twin rather than a curve-fit: the mechanistic ODE/PK-PD path in
// mechanistic.ts is ALWAYS the base. The surrogate never produces a prediction. It produces a DELTA on
// top of the mechanistic prediction, and that delta is then adjudicated by the reconciliation gate. The
// API here has no function that returns an absolute value — that is the structural enforcement of
// "residual, not replacement".
//
// Deliberately small and honest. This is a ridge-regularised linear model over 3–4 clinically observable
// covariates per organ, fitted in closed form (normal equations, no gradient descent, no random
// initialisation) on the synthetic fixture cohort. It is not, and is not pretending to be, a trained
// neural surrogate. A large model here would be a fake: we have no real cohort to train one on, and the
// point of W10 is the RECONCILIATION CONTRACT, not the model class. When a real cohort exists, the
// contract below is what a bigger model would have to satisfy — unchanged.
import { type Compartment } from './mechanistic.js';
import { buildCohort, mechanisticFor, SAMPLE_DAYS, HORIZON_DAYS, COHORT_ID, COHORT_VERSION, type CohortSubject } from './cohort.js';
import { canonical, digest, q } from './seal.js';

export const SURROGATE_ID = 'organ-residual-ridge';
export const SURROGATE_VERSION = 'v1';
const LAMBDA = 1e-3;

/** A feature is a named, pure function of the observable covariates and the point in the horizon. */
interface Feature { name: string; of: (cv: CohortSubject['covariates'], dayFrac: number) => number }

/**
 * Per-organ feature sets. Each covariate is something a clinic routinely has and the mechanistic model
 * does NOT consume — that is the whole justification for a learned term existing at all.
 */
const FEATURES: Record<Compartment, Feature[]> = {
  // SBP residual is driven by how much drug is actually taken and how responsive the renin axis is.
  cardio: [
    { name: 'adherencePdc', of: (c) => c.adherencePdc },
    { name: 'reninIndex', of: (c) => c.reninIndex },
    { name: 'dayFrac', of: (_c, d) => d },
  ],
  // A1c residual accumulates with time and scales with adiposity.
  hepatic: [
    { name: 'bmi', of: (c) => c.bmi },
    { name: 'dayFrac', of: (_c, d) => d },
    { name: 'bmi×dayFrac', of: (c, d) => c.bmi * d },
  ],
  // eGFR residual is a RATE effect: albuminuria × elapsed time.
  renal: [
    { name: 'uacr', of: (c) => c.uacr },
    { name: 'dayFrac', of: (_c, d) => d },
    { name: 'uacr×dayFrac', of: (c, d) => c.uacr * d },
  ],
};

export interface OrganResidualModel {
  compartment: Compartment;
  features: string[];
  /** [intercept, ...per-feature weights] on STANDARDISED features. */
  coefficients: number[];
  /** Standardisation constants, computed on the TRAIN split only (no test leakage). */
  center: number[];
  scale: number[];
  lambda: number;
  /** Residual RMSE on the train split, in observable units — reported for honesty, not for boasting. */
  trainRmse: number;
  n: number;
}

export interface Surrogate {
  id: string;
  version: string;
  fittedOn: { cohort: string; cohortVersion: string; subjects: number; trainSubjects: number; horizonDays: number; synthetic: true };
  organs: Record<Compartment, OrganResidualModel>;
  /** Content address of the fitted weights — this is what the prediction seal binds to. */
  coefficientsDigest: string;
}

// ── closed-form ridge ────────────────────────────────────────────────────────────────────────────

/** Solve A w = b by Gaussian elimination with partial pivoting. k ≤ 5 here. */
function solve(A: number[][], b: number[]): number[] {
  const k = b.length;
  const M = A.map((row, i) => [...row, b[i]!]);
  for (let col = 0; col < k; col++) {
    let piv = col;
    for (let r = col + 1; r < k; r++) if (Math.abs(M[r]![col]!) > Math.abs(M[piv]![col]!)) piv = r;
    if (Math.abs(M[piv]![col]!) < 1e-14) throw new Error(`singular normal equations at column ${col}`);
    [M[col], M[piv]] = [M[piv]!, M[col]!];
    for (let r = 0; r < k; r++) {
      if (r === col) continue;
      const f = M[r]![col]! / M[col]![col]!;
      for (let c2 = col; c2 <= k; c2++) M[r]![c2]! -= f * M[col]![c2]!;
    }
  }
  return M.map((row, i) => row[k]! / row[i]!);
}

/** Ridge on standardised features; the intercept is never penalised. */
function ridge(X: number[][], y: number[], lambda: number): number[] {
  const k = X[0]!.length;
  const A: number[][] = Array.from({ length: k }, () => new Array(k).fill(0));
  const b: number[] = new Array(k).fill(0);
  for (let i = 0; i < X.length; i++) {
    for (let a = 0; a < k; a++) {
      b[a]! += X[i]![a]! * y[i]!;
      for (let c = 0; c < k; c++) A[a]![c]! += X[i]![a]! * X[i]![c]!;
    }
  }
  for (let a = 1; a < k; a++) A[a]![a]! += lambda * X.length; // a=0 is the intercept: unpenalised
  return solve(A, b);
}

// ── fitting ──────────────────────────────────────────────────────────────────────────────────────

/** Rows of (features, residual) for one organ over the subjects given. */
function rows(subjects: CohortSubject[], k: Compartment): { raw: number[][]; y: number[] } {
  const feats = FEATURES[k];
  const raw: number[][] = [], y: number[] = [];
  for (const s of subjects) {
    const mech = mechanisticFor(s)[k];
    SAMPLE_DAYS.forEach((d, i) => {
      const dayFrac = d / HORIZON_DAYS;
      raw.push(feats.map((f) => f.of(s.covariates, dayFrac)));
      y.push(s.truth[k][i]! - mech[i]!); // the RESIDUAL: what the physics missed
    });
  }
  return { raw, y };
}

function fitOrgan(train: CohortSubject[], k: Compartment): OrganResidualModel {
  const { raw, y } = rows(train, k);
  const m = raw[0]!.length;
  const center = Array.from({ length: m }, (_, j) => raw.reduce((a, r) => a + r[j]!, 0) / raw.length);
  const scale = Array.from({ length: m }, (_, j) => {
    const v = raw.reduce((a, r) => a + (r[j]! - center[j]!) ** 2, 0) / raw.length;
    return Math.sqrt(v) || 1;
  });
  const X = raw.map((r) => [1, ...r.map((v, j) => (v - center[j]!) / scale[j]!)]);
  const coefficients = ridge(X, y, LAMBDA);
  const pred = X.map((r) => r.reduce((a, v, j) => a + v * coefficients[j]!, 0));
  const trainRmse = Math.sqrt(pred.reduce((a, p, i) => a + (p - y[i]!) ** 2, 0) / y.length);
  return {
    compartment: k, features: FEATURES[k].map((f) => f.name),
    coefficients: coefficients.map((c) => q(c, 8)),
    center: center.map((c) => q(c, 8)), scale: scale.map((c) => q(c, 8)),
    lambda: LAMBDA, trainRmse: q(trainRmse, 6), n: y.length,
  };
}

let CACHED: Surrogate | null = null;

/** Fit (once per process) the residual surrogate for every organ on the cohort's TRAIN split. */
export function fitSurrogate(): Surrogate {
  if (CACHED) return CACHED;
  const cohort = buildCohort();
  const train = cohort.filter((s) => s.split === 'train');
  const organs = {
    cardio: fitOrgan(train, 'cardio'),
    hepatic: fitOrgan(train, 'hepatic'),
    renal: fitOrgan(train, 'renal'),
  } as Record<Compartment, OrganResidualModel>;
  CACHED = {
    id: SURROGATE_ID, version: SURROGATE_VERSION,
    fittedOn: { cohort: COHORT_ID, cohortVersion: COHORT_VERSION, subjects: cohort.length, trainSubjects: train.length, horizonDays: HORIZON_DAYS, synthetic: true },
    organs,
    coefficientsDigest: digest(canonical(organs)),
  };
  return CACHED;
}

/**
 * The surrogate's PROPOSAL: a delta in observable units, to be added to the mechanistic prediction.
 * Note what is missing — there is no `predict()` that returns an absolute value. The surrogate cannot
 * express a prediction on its own; it can only propose a correction, which the gate may refuse.
 */
export function proposeDelta(sur: Surrogate, k: Compartment, cv: CohortSubject['covariates'], dayFrac: number): number {
  const m = sur.organs[k];
  const raw = FEATURES[k].map((f) => f.of(cv, dayFrac));
  const x = [1, ...raw.map((v, j) => (v - m.center[j]!) / m.scale[j]!)];
  return x.reduce((a, v, j) => a + v * m.coefficients[j]!, 0);
}

/** Covariate vector for the seed twin. Synthetic, like the rest of the seed subject. */
export const SEED_COVARIATES = { adherencePdc: 0.86, reninIndex: 0.42, bmi: 28.4, uacr: 0.18 };
