// W10 proof harness — the tests that carry the argument, not tests that carry coverage.
// Run: `npx tsx src/dynamics/verify.ts`. Exits non-zero on any failure; wired into ci.yml.
//
// What is being argued:
//   A. the mechanistic base is a real integrated model (mass balance holds, it reproduces the person's
//      own recorded state at day 0, and its qualitative behaviour matches the physiology it encodes);
//   B. the surrogate is a RESIDUAL — remove its proposal and you get the physics back, exactly;
//   C. the gate ACCEPTS an admissible correction;
//   D. the gate REJECTS an inadmissible one with the correct TYPED reason — every reason reachable;
//   E. a rejection is RECORDED, not silently clamped (the emitted value is the physics, NOT the bound);
//   F. the seal is deterministic, verifiable, and genuinely binds model + surrogate + gate policy;
//   G. the residual measurably improves fit on HELD-OUT synthetic subjects (reported, not asserted).
import { simulate, anchorTo, massImbalance, DEFAULT_PARAMS, SIGMA, OBSERVABLE, type Compartment } from './mechanistic.js';
import { buildCohort, mechanisticFor, SAMPLE_DAYS, HORIZON_DAYS } from './cohort.js';
import { fitSurrogate, proposeDelta } from './surrogate.js';
import {
  reconcile, auditEmission, rejectionLedger, _clearLedger, gatePolicy, EMISSION_LAW,
  RANGE, MAX_RATE_PER_DAY, ENVELOPE_K, REJECTION_REASONS, type RejectionReason, type ReconciliationVerdict,
} from './gate.js';
import { predict, verifyPrediction, currentObservations, EmissionLawViolation } from './predict.js';
import { seal, canonical, digest } from './seal.js';

let failures = 0;
const ok = (cond: boolean, msg: string) => { console.log(`  ${cond ? '✓' : '✗'} ${msg}`); if (!cond) failures++; };
const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

// ── A. the mechanistic base is a real model ──────────────────────────────────────────────────────
console.log('\n▶ A — MECHANISTIC BASE (organ compartment ODE / PK-PD)');
{
  const observed = currentObservations();
  const params = anchorTo(observed, DEFAULT_PARAMS);
  const run = simulate(180, params);

  const worstMass = Math.max(...run.steps.map(massImbalance));
  ok(worstMass < 1e-8, `drug mass balance holds across 180 days (worst imbalance ${worstMass.toExponential(2)} mg of a ${run.steps.at(-1)!.mass.doseIn.toFixed(0)} mg ledger)`);

  const d0 = run.steps[0]!;
  ok(Math.abs(d0.sbp - observed.sbp!) < 1e-6, `day 0 reproduces the person's own recorded SBP (${d0.sbp.toFixed(3)} vs ${observed.sbp})`);
  ok(Math.abs(d0.a1c - observed.a1c!) < 1e-6, `day 0 reproduces the recorded A1c (${d0.a1c.toFixed(3)} vs ${observed.a1c})`);
  ok(Math.abs(d0.egfr - observed.egfr!) < 1e-6, `day 0 reproduces the recorded eGFR (${d0.egfr.toFixed(3)} vs ${observed.egfr})`);

  ok(run.steps.every((s) => s.drugEffect >= 0), 'the ACE-inhibitor PD term is never negative (it cannot raise pressure)');
  ok(run.steps.every((s) => s.sbp <= s.sbpUntreated + 1e-9), 'the treated trajectory never sits above the untreated trajectory');
  ok(run.steps.every((s, i) => i === 0 || s.egfr <= run.steps[i - 1]!.egfr + 1e-12), 'eGFR is non-increasing (nephron mass does not regenerate)');

  // A1c must move TOWARD the ADAG equilibrium for the falling mean glucose, at the RBC-pool rate
  const a1cEq = (mg: number) => (mg + 46.7) / 28.7;
  const last = run.steps.at(-1)!;
  ok(last.a1c < d0.a1c && last.a1c > a1cEq(last.meanGlucose) - 0.01,
    `A1c relaxes toward the ADAG equilibrium without overshooting (${d0.a1c.toFixed(2)} → ${last.a1c.toFixed(2)}, equilibrium ${a1cEq(last.meanGlucose).toFixed(2)})`);

  // a doubled dose must not produce more than the Emax asymptote — saturation is real
  const doubled = simulate(30, { ...params, cardio: { ...params.cardio, doseMg: params.cardio.doseMg * 2 } });
  ok(doubled.steps.at(-1)!.drugEffect <= params.cardio.Emax + 1e-9,
    `doubling the dose cannot exceed the Emax asymptote (${doubled.steps.at(-1)!.drugEffect.toFixed(2)} ≤ ${params.cardio.Emax} mmHg)`);
}

// ── B. the surrogate is a residual, not a replacement ────────────────────────────────────────────
console.log('\n▶ B — THE SURROGATE IS A RESIDUAL');
{
  const sur = fitSurrogate();
  ok(!('predict' in sur) && typeof (fitSurrogate as any).predictAbsolute !== 'function',
    'the surrogate module exposes no absolute-prediction API — it can only propose a delta');
  ok(sur.fittedOn.synthetic === true, 'the surrogate declares its cohort SYNTHETIC in its own provenance');

  // zero the proposal and the emitted trajectory must be the mechanistic one, exactly
  const zeroed = predict({ overrideDelta: () => 0 });
  const same = zeroed.organs.every((o) => o.emitted.every((v, i) => v === o.mechanistic[i]));
  ok(same, 'with a zero residual the emitted trajectory IS the mechanistic trajectory, bit for bit');
  ok(zeroed.gate.rejected === 0, 'a zero residual is always admissible');

  const live = predict();
  const moved = live.organs.some((o) => o.emitted.some((v, i) => v !== o.mechanistic[i]));
  ok(moved, 'with the fitted residual the emitted trajectory actually differs from the physics (the surrogate is doing something)');
}

// ── C + D + E. the gate ──────────────────────────────────────────────────────────────────────────
console.log('\n▶ C — THE GATE ACCEPTS AN ADMISSIBLE CORRECTION');
{
  _clearLedger();
  const p = predict({ overrideDelta: (k) => (k === 'cardio' ? 1.5 : k === 'hepatic' ? 0.01 : -0.05) });
  ok(p.gate.rejected === 0 && p.gate.accepted > 0, `all ${p.gate.accepted} in-bounds proposals accepted, 0 rejected`);
  const cardio = p.organs.find((o) => o.compartment === 'cardio')!;
  ok(cardio.emitted.slice(1).every((v, i) => Math.abs(v - (cardio.mechanistic[i + 1]! + 1.5)) < 1e-6),
    'an accepted proposal is emitted WHOLE (mechanistic + the full delta), not attenuated');
  ok(rejectionLedger().count === 0, 'nothing is written to the rejection ledger when nothing is rejected');
}

console.log('\n▶ D — THE GATE REJECTS WITH A TYPED REASON (one case per reason)');
const seen = new Set<RejectionReason>();
{
  // Each case is built to break exactly one law while staying legal under the others, so the reported
  // reason is the law that was actually broken and not an artefact of rule ordering.
  const cases: { name: string; k: Compartment; delta: number; expect: RejectionReason; stepDays?: number }[] = [
    { name: 'NaN proposal', k: 'cardio', delta: NaN, expect: 'nonfinite' },
    { name: `SBP driven below the ${RANGE.cardio.lo} mmHg floor`, k: 'cardio', delta: -100, expect: 'range' },
    { name: 'A1c jumps faster than the red-cell pool can turn over', k: 'hepatic', delta: 3.0, expect: 'conservation' },
    { name: 'SBP pushed above the untreated baseline (ACE inhibitor raising pressure)', k: 'cardio', delta: 15, expect: 'monotonicity' },
    { name: 'eGFR rises (nephrons regenerating)', k: 'renal', delta: 0.6, expect: 'monotonicity' },
    { name: `eGFR falls faster than ${MAX_RATE_PER_DAY.renal} mL/min/day`, k: 'renal', delta: -8, expect: 'rate' },
    { name: `correction exceeds ${ENVELOPE_K}σ of the mechanistic model's own uncertainty`, k: 'cardio', delta: -13, expect: 'envelope' },
  ];
  for (const c of cases) {
    _clearLedger();
    const p = predict({ compartments: [c.k], stepDays: c.stepDays ?? 7, overrideDelta: (k, _d) => (k === c.k ? c.delta : 0) });
    const organ = p.organs.find((o) => o.compartment === c.k)!;
    const first = organ.decisions[0]!;
    const right = first.verdict === 'rejected' && first.reason === c.expect;
    ok(right, `${c.name} → rejected as '${first.reason ?? first.verdict}' (expected '${c.expect}')`);
    if (right) {
      seen.add(c.expect);
      console.log(`      law: ${first.law}`);
      console.log(`      bound: ${first.bound}  ·  measured ${first.measured?.got} vs limit ${first.measured?.limit} ${first.measured?.units}`);
    }
  }

  const unreachable = REJECTION_REASONS.filter((r) => !seen.has(r));
  ok(unreachable.length === 0, `every typed rejection reason is reachable (unexercised: ${unreachable.join(', ') || 'none'})`);
}

console.log('\n▶ E — A REJECTION IS RECORDED, NOT SILENTLY CLAMPED');
{
  _clearLedger();
  // Drive SBP to 38 mmHg: below the 60 mmHg floor. A clamping gate would emit 60. This one must emit
  // the physics and say so.
  const p = predict({ compartments: ['cardio'], overrideDelta: () => -100 });
  const organ = p.organs.find((o) => o.compartment === 'cardio')!;
  const d = organ.decisions[0]!;

  ok(d.verdict === 'rejected' && d.reason === 'range', 'the out-of-range proposal is rejected');
  ok(d.emitted === d.mechanistic, `the emitted value IS the mechanistic value (${d.emitted}), not the proposal`);
  ok(d.emitted !== RANGE.cardio.lo, `the emitted value is NOT the boundary ${RANGE.cardio.lo} — a clamp would have produced exactly that`);
  ok(d.clamped === false, 'the decision states clamped: false');
  ok(d.proposed !== d.emitted && Number.isFinite(d.proposed), `the refused proposal survives in the record (${d.proposed})`);
  ok(!!d.law && !!d.bound && !!d.measured, 'the rejection carries the law it broke, the bound, and the measured violation');

  // the rejection is visible in three places: the organ, the response envelope, and the ledger
  ok(organ.rejected === organ.decisions.length && organ.byReason.range === organ.rejected, 'the organ block counts the rejections by reason');
  ok(p.gate.rejected > 0 && p.gate.rejections.length === p.gate.rejected, 'the response envelope carries every rejection in full');
  const led = rejectionLedger();
  ok(led.count === p.gate.rejected && led.byReason.range === p.gate.rejected, `the rejection ledger recorded all ${led.count} refusals`);
  ok(led.rejections.every((r) => r.predictionId === p.receipt.id), 'every ledger entry is keyed to the sealed prediction it came from');

  // and the whole trajectory is the physics — a refused correction leaves NO trace in the numbers
  ok(organ.emitted.every((v, i) => v === organ.mechanistic[i]), 'a fully-rejected organ emits exactly the mechanistic trajectory');
  ok(organ.emissionAudit === 'ok', 'the gate self-audit passes on the fallback trajectory');
}

console.log('\n▶ E2 — THE ANTI-CLAMP LAW IS AUDITED, NOT ASSUMED');
{
  // A clamping gate is what we are guarding against, so build one by hand and prove the audit catches
  // it. The forged decision emits the BOUNDARY (60 mmHg) for a proposal of 38 — exactly the plausible,
  // silent output a clamp produces.
  const honest = reconcile({
    compartment: 'cardio', day: 7, dtDays: 7, mechanistic: 138, previousEmitted: 138,
    proposed: 38, delta: -100, step: { day: 7, sbp: 138, sbpUntreated: 147.65, drugEffect: 9.65, concentration: 0.0076, a1c: 5.9, meanGlucose: 123, egfr: 92, mass: { doseIn: 0, gut: 0, central: 0, cleared: 0, neverAbsorbed: 0 } }, params: DEFAULT_PARAMS,
  });
  ok(honest.verdict === 'rejected' && honest.emitted === 138, 'the real gate emits the physics for an out-of-range proposal');
  ok(auditEmission([honest]).ok === true, 'the audit passes an honest rejection');

  const forged = { ...honest, emitted: RANGE.cardio.lo };   // <- the silent clamp
  const caught = auditEmission([forged]);
  ok(caught.ok === false, `the audit CATCHES a decision that emitted the boundary ${RANGE.cardio.lo} instead of the physics`);
  if (caught.ok === false) {
    ok(caught.violations.length === 1 && caught.violations[0]!.emitted === RANGE.cardio.lo, 'the audit names the clamped value');
    ok(caught.law === EMISSION_LAW, 'the audit cites the anti-clamp law');
  }

  const forgedAccept = { ...honest, verdict: 'accepted' as const, emitted: 100 }; // neither physics nor proposal
  ok(auditEmission([forgedAccept]).ok === false, 'the audit also catches a partially-applied ACCEPTED correction');

  // and every organ of a live prediction passes the audit
  const live = predict();
  ok(live.organs.every((o) => o.emissionAudit === 'ok'), 'every organ of a live prediction passes the anti-clamp audit');
}

console.log('\n▶ E3 — THE VERDICT USES THE VOCABULARY THE BODY-STATE SCHEMA ALREADY DECLARES');
{
  // human-digital-twin's body-state-model.schema.json declares dynamical_model.reconciliation and the
  // safety invariant that goes with it. The schema had the contract and no executable model; this is
  // the executable half, so it speaks the schema's words rather than inventing a parallel vocabulary.
  const applied = predict();
  ok(applied.reconciliation.verdict === 'physics_adjusted', `admissible corrections applied -> '${applied.reconciliation.verdict}'`);
  ok(applied.reconciliation.executionDecision === 'allow' && applied.reconciliation.humanActuation === 'permitted', 'an adjusted run permits actuation');

  const untouched = predict({ overrideDelta: () => 0 });
  ok(untouched.reconciliation.verdict === 'physics_verified', `a correction that moves nothing -> '${untouched.reconciliation.verdict}'`);

  const refused = predict({ compartments: ['cardio'], overrideDelta: () => -100 });
  ok(refused.reconciliation.verdict === 'divergent', `a refused proposal -> '${refused.reconciliation.verdict}'`);
  ok(refused.reconciliation.executionDecision === 'deny', 'divergent fails CLOSED: ExecutionDecision = deny');
  ok(refused.reconciliation.humanActuation === 'blocked' && refused.reconciliation.omegaCeiling === 'TRUSTED',
    'divergent blocks human actuation and caps omega at TRUSTED — the schema safety invariant, emitted rather than left to be looked up');
  ok(refused.reconciliation.schema.includes('body-state-model.schema.json'), 'the verdict cites the schema it came from');

  const REC: ReconciliationVerdict[] = ['physics_verified', 'physics_adjusted', 'learned_only', 'divergent', 'not_run'];
  ok(REC.includes(applied.reconciliation.verdict) && REC.includes(refused.reconciliation.verdict),
    'every emitted verdict is inside the schema enum');
  // 'learned_only' is unreachable BY CONSTRUCTION and that is the point: physics always runs first.
  const anyLearnedOnly = [applied, untouched, refused].some((p) => p.reconciliation.verdict === 'learned_only');
  ok(!anyLearnedOnly, "'learned_only' is unreachable — the mechanistic model always runs and the surrogate cannot express an absolute value");
}

console.log('\n▶ E4 — THE ANTI-CLAMP AUDIT IS INSIDE THE SEAL, AND IT FAILS CLOSED');
{
  // The audit used to only pick which literal went into a field, and the sealed projection EXCLUDED
  // that field — so a clamped run and an honest run produced the same digest and the violation was
  // unprovable from the receipt afterwards. Both halves are asserted here: bound, and acted on.
  const p = predict();
  ok(verifyPrediction(p), 'a clean prediction verifies against its own receipt');

  const tampered = structuredClone(p) as typeof p;
  (tampered.organs[0] as { emissionAudit: unknown }).emissionAudit = {
    violated: 'clamp', law: EMISSION_LAW,
    violations: [{ compartment: 'cardio', day: 7, emitted: RANGE.cardio.lo, mechanistic: 138, proposed: 38 }],
  };
  ok(!verifyPrediction(tampered),
    'flipping emissionAudit from ok to a clamp violation BREAKS the seal — the violation is provable from the receipt');

  const flipped = structuredClone(p) as typeof p;
  flipped.reconciliation = { ...flipped.reconciliation, executionDecision: 'allow', humanActuation: 'permitted', verdict: 'physics_verified' };
  ok(!verifyPrediction(flipped),
    'flipping the reconciliation verdict deny→allow BREAKS the seal — the safety verdict is BOUND, not merely derivable');

  // now a gate that genuinely clamps: it emits the BOUNDARY instead of the physics. predict() must
  // seal it (so it is provable) and then REFUSE it (so the clamped number never reaches a caller).
  let thrown: EmissionLawViolation | null = null;
  try {
    predict({
      compartments: ['cardio'], overrideDelta: () => -100,
      overrideDecisions: (_k, ds) => ds.map((d) => ({ ...d, emitted: RANGE.cardio.lo })),
    });
  } catch (e) { thrown = e instanceof EmissionLawViolation ? e : null; }
  ok(thrown !== null, 'a gate that clamps makes predict() THROW — a clamped prediction is never returned');
  if (thrown) {
    ok(thrown.law === EMISSION_LAW, 'the refusal cites the anti-clamp law');
    ok(thrown.violations.some((v) => v.compartment === 'cardio'), 'the refusal names the compartment that clamped');
    ok(/^ht-prediction-[0-9a-f]{64}$/.test(thrown.receipt.id),
      'the prediction was SEALED BEFORE it was refused — the receipt exists, so the violation is provable after the fact');
    const honest = predict({ compartments: ['cardio'], overrideDelta: () => -100 });
    ok(thrown.receipt.snapshotDigest !== honest.receipt.snapshotDigest,
      'the clamped run and the honest run seal DIFFERENTLY (before this fix they were identical)');
  }
}

console.log('\n▶ E5 — THE DENY VERDICT IS REACHABLE FROM CALLER INPUT ALONE (no test hook)');
{
  // This is why the unwired verdict mattered. `covariates` is read straight off the POST body in
  // server.ts, and the surrogate consumes it — so an ordinary caller can drive the proposal across the
  // admissibility bounds and make the run divergent. No overrideDelta, no privileged access.
  const live = predict({ covariates: { adherencePdc: 50, reninIndex: 50, bmi: 28.4, uacr: 0.18 } });
  ok(live.reconciliation.verdict === 'divergent',
    `caller-supplied covariates alone drive the run divergent (got '${live.reconciliation.verdict}', ${live.gate.rejected} refusals)`);
  ok(live.reconciliation.executionDecision === 'deny' && live.reconciliation.humanActuation === 'blocked' && live.reconciliation.omegaCeiling === 'TRUSTED',
    'that run carries deny / blocked / TRUSTED — the verdict the request path must act on');
  ok(live.organs.every((o) => o.emitted.every((v, i) => Number.isFinite(v) && Number.isFinite(o.mechanistic[i]!))),
    'the divergent run still carries a readable mechanistic trajectory (the refusal is about actuation, not about reading)');

  const ordinary = predict();
  ok(ordinary.reconciliation.executionDecision === 'allow',
    'TEETH THE OTHER WAY — the default covariates still produce an ALLOWED prediction, so the gate is not simply refusing everything');
}

// ── F. the seal ──────────────────────────────────────────────────────────────────────────────────
console.log('\n▶ F — THE SEAL (sha256 over output + snapshot binding)');
{
  const a = predict();
  const b = predict();
  ok(a.receipt.snapshotDigest === b.receipt.snapshotDigest, 'identical inputs produce an identical seal (deterministic)');
  ok(/^sha256-[0-9a-f]{64}$/.test(a.receipt.snapshotDigest), 'the snapshot digest is sha256-<64 hex> — the label matches the math');
  ok(/^ht-prediction-[0-9a-f]{64}$/.test(a.receipt.id), 'the receipt id is the estate shape ht-<kind>-<sha256>');
  ok(verifyPrediction(a), 'the seal re-derives from the prediction contents (verifiable, not decorative)');

  const c = predict({ horizonDays: 120 });
  ok(c.receipt.snapshotDigest !== a.receipt.snapshotDigest, 'a different horizon produces a different seal');

  // the snapshot genuinely BINDS the provenance: change the surrogate version or the gate policy digest
  // in the provenance block and the seal must move
  const parts = (prov: unknown) => seal('prediction', { x: 1 }, { y: 2 }, prov).snapshotDigest;
  const base = parts(a.provenance);
  ok(parts({ ...a.provenance, surrogate: { ...a.provenance.surrogate, coefficientsDigest: 'sha256-' + '0'.repeat(64) } }) !== base,
    'changing the surrogate weight digest changes the seal (the surrogate version is BOUND)');
  ok(parts({ ...a.provenance, gate: { ...a.provenance.gate, admissibilityDigest: 'sha256-' + '0'.repeat(64) } }) !== base,
    'changing the gate policy digest changes the seal (the admissibility rules are BOUND)');
  ok(parts({ ...a.provenance, mechanistic: { ...a.provenance.mechanistic, version: 'v99' } }) !== base,
    'changing the mechanistic model version changes the seal');

  // canonical JSON: key order must not change the digest
  ok(digest(canonical({ a: 1, b: 2 })) === digest(canonical({ b: 2, a: 1 })), 'canonical JSON is key-order independent');
  ok(a.provenance.surrogate.residualOnly === true, 'the receipt asserts the surrogate is residual-only');
  ok(a.provenance.gate.admissibilityDigest === gatePolicy().admissibilityDigest, 'the receipt binds the live gate policy');
  ok(a.disclaimer.includes('Not a diagnosis'), 'a prediction that can reach a surface carries the non-diagnostic frame');
}

// ── G. does the residual actually improve the fit? (measured, on held-out subjects) ──────────────
console.log('\n▶ G — RESIDUAL vs MECHANISTIC-ALONE, on HELD-OUT synthetic subjects');
const fit: Record<string, { rmseM: number; rmseR: number; maeM: number; maeR: number; n: number }> = {};
{
  const sur = fitSurrogate();
  const test = buildCohort().filter((s) => s.split === 'test');
  for (const k of ['cardio', 'hepatic', 'renal'] as Compartment[]) {
    let seM = 0, seR = 0, aeM = 0, aeR = 0, n = 0;
    for (const s of test) {
      const mech = mechanisticFor(s)[k];
      SAMPLE_DAYS.forEach((d, i) => {
        const y = s.truth[k][i]!, m = mech[i]!;
        const r = m + proposeDelta(sur, k, s.covariates, d / HORIZON_DAYS);
        seM += (y - m) ** 2; seR += (y - r) ** 2; aeM += Math.abs(y - m); aeR += Math.abs(y - r); n++;
      });
    }
    fit[k] = { rmseM: Math.sqrt(seM / n), rmseR: Math.sqrt(seR / n), maeM: aeM / n, maeR: aeR / n, n };
    const f = fit[k]!;
    const rel = 1 - f.rmseR / f.rmseM;
    console.log(`  ${k.padEnd(8)} n=${f.n}  RMSE ${f.rmseM.toFixed(4)} → ${f.rmseR.toFixed(4)} ${OBSERVABLE[k].unit}  (${rel >= 0 ? '' : '+'}${pct(-rel).replace('-', '')} ${rel >= 0 ? 'better' : 'WORSE'})   MAE ${f.maeM.toFixed(4)} → ${f.maeR.toFixed(4)}   [mech σ ${SIGMA[k]}]`);
  }
  // The claim we are willing to make: cardio and hepatic improve materially; renal does NOT, because
  // over a 90-day horizon the albuminuria-driven divergence (< 0.5 mL/min) sits far below the assay
  // noise (1.6 mL/min 1σ). That is a fact about eGFR, not a bug — and the floor says so rather than
  // being tuned until the number looks good.
  ok(1 - fit.cardio!.rmseR / fit.cardio!.rmseM > 0.20, `cardio residual improves held-out RMSE by >20% (measured ${pct(1 - fit.cardio!.rmseR / fit.cardio!.rmseM)})`);
  ok(1 - fit.hepatic!.rmseR / fit.hepatic!.rmseM > 0.15, `hepatic residual improves held-out RMSE by >15% (measured ${pct(1 - fit.hepatic!.rmseR / fit.hepatic!.rmseM)})`);
  ok(fit.renal!.rmseR <= fit.renal!.rmseM * 1.02, `renal residual does NOT degrade held-out RMSE (measured ${pct(1 - fit.renal!.rmseR / fit.renal!.rmseM)} — signal is below assay noise at a 90-day horizon; this is reported, not fixed)`);
}

console.log(`\n${failures === 0
  ? '✓ W10 TWIN DYNAMICS PROVEN — mechanistic base integrates, the surrogate is a residual, the gate rejects with typed reasons and records every refusal, and the seal binds model + surrogate + policy'
  : `✗ ${failures} assertion(s) failed`}`);
process.exit(failures === 0 ? 0 : 1);
