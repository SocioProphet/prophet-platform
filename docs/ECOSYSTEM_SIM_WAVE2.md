# Ecosystem Simulation Substrate — Wave 2 (solver, Layer B)

Builds on the merged Wave-1 causal spine (#1220, `tools/causal_identification.py`).
Wave 1 is Layer A (*may we claim this*); Wave 2 is Layer B (*what is the value*),
and it runs **only** through `causal_identification.gate` — no number without a
cleared estimand.

## `tools/scenario_solver.py`

- **ParameterFact** — a parameter as a fact: value + `interval` (uncertainty) + `n`
  + provenance + `epistemic_level` + `as_of`. Uncertainty propagates into output.
- **solve(spec)**:
  1. `identify()` the estimand. If **not clearable**, REFUSE the point estimate —
     return non-causal `bounds`, `blocking_structure`, and `measurement_to_identify`
     (no distribution).
  2. If cleared, Monte-Carlo propagate parameter uncertainty (deterministic per
     `seed`) → a **Distribution** (`p05/p50/p95/mean`). Never a scalar.
- **content_address** over `{graph_snapshot_hash, intervention_set, solver_version,
  assumption_set, reaction_level, parameter_vintage, seed}` → certified scenarios
  **replay bit-identically** (the liability shield, spec §7).
- **Reaction level** is declared on every result; **L0** (static competitors) is
  labelled `upper_bound_on_own_move` — never a forecast; **L1** dampens via a
  `competitor_reaction` parameter. `propagation` is pluggable so the real Wave-2/4
  solvers (discrete-event supply, choice model, best-response) drop in unchanged.

## Acceptance coverage (spec §12)

| Criterion | Test |
|---|---|
| No point estimate for an unidentified estimand | `test_unidentified_refuses_point_estimate` |
| Every output a distribution with propagated uncertainty | `test_identified_returns_a_distribution_not_a_scalar`, `test_parameter_uncertainty_propagates` |
| Certified scenarios replay bit-identically | `test_deterministic_replay_is_bit_identical` |
| Reaction level declared; L0 labelled a bound | `test_L0_is_labelled_a_bound_and_L1_reacts` |

## Next

Wave-2 remainder: discrete-event supply propagation + choice model as concrete
`propagation` plugins; scenario-artifact persistence. Wave 3: precomputed
sensitivity, read-set delta invalidation, staleness decay.
