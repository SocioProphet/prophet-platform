# PROMETHEUS Optional PySR Execution

Status: v0.1 implementation plan.

This tranche prepares the next step after the MVP linear fallback: optional real PySR execution behind the same `EquationCandidate` artifact contract.

## Position

Real PySR execution must be optional at platform level until Julia, PySR, and SymbolicRegression.jl runtime posture are pinned.

The platform contract remains stable:

- emit `EquationCandidate`;
- include dataset URI and SHA-256 content hash;
- include method family, implementation mode, fit metric, complexity, units status, promotion state, and non-authority declaration;
- never admit laws, ontology assertions, policy, or controllers from runtime output alone.

## Execution modes

The current MVP supports:

- `mvp_linear_fallback`

The next implementation should add:

- `optional_pysr`

`optional_pysr` is eligible only when the runtime environment has PySR and its Julia backend available. If unavailable, the tool must fail closed or explicitly fall back to `mvp_linear_fallback` when the caller requested fallback behavior.

## Required PySR output mapping

A PySR run should map to the existing candidate contract:

- best expression or Pareto-front expression to `equationLatex`;
- normalized mean squared error to `fitMetric`;
- expression complexity to `complexity`;
- configured operators to future AgentPlane `operatorLibrary` handoff;
- package versions to future AgentPlane replay artifact;
- candidate remains `promotionState: candidate` unless units are inconsistent, in which case it is `rejected`.

## Non-goals

This plan does not make PySR a required dependency for CI.

This plan does not install Julia in platform workflows.

This plan does not create AgentPlane replay artifacts directly.

This plan does not promote candidates to SRAssertionProposal.

## Acceptance criteria for next code tranche

- CLI accepts `--engine mvp_linear_fallback|optional_pysr`.
- `optional_pysr` attempts to import PySR lazily.
- Missing PySR fails closed unless fallback is explicitly allowed.
- Output artifact shape remains backward compatible with the MVP artifact validator.
- CI continues to validate the fallback path without requiring PySR/Juila.
