# PROMETHEUS Neuro-Symbolic Kernel

Status: v0.1 platform contract tranche.

PROMETHEUS is the owning integration plane for neuro-symbolic discovery in Prophet Platform. IBM's Neuro-Symbolic AI Toolkit is useful prior art and a research index, but it is not a platform dependency, not a vendor runtime, and not an authority plane in this stack.

The kernel starts with PROMETHEUS candidate emission and ends with PROMETHEUS evidence-bound proposal handling:

```text
Observation or dataset corpus
  -> PROMETHEUS discovery engine
  -> candidate artifact
  -> PROMETHEUS neuro-symbolic run artifact
  -> AgentPlane replay/evidence reference
  -> automated gate or human review surface
  -> Ontogenesis semantic proposal
  -> governance decision
```

## Position

PROMETHEUS may integrate neuro-symbolic methods as discovery engines, candidate factories, verification helpers, semantic grounding helpers, or experimental-design helpers.

PROMETHEUS must not treat any engine output as a law, ontology assertion, policy, controller, deployment authorization, memory promotion, or canonical schema. Every output remains candidate material until replay, dimensional analysis, semantic validation, and governance review are complete.

## Initial capability map

| Capability lane | Prior-art source | PROMETHEUS role | First artifact |
|---|---|---|---|
| symbolic scientific discovery | AI Descartes-style law discovery | primary discovery-engine family | `EquationCandidate` / `ProgramCandidate` |
| logical truth-bound reasoning | LNN-style formula bounds | advisory verification and contradiction surfacing | `TruthBoundObservation` |
| language-to-logic grounding | AMR-to-logic-style semantic parsing | source-to-logic candidate generator | `LogicCandidate` |
| commonsense/knowledge graph substrate | ULKB / ERGO-style substrate | evidence and background-theory lookup | `KnowledgeSubstrateRef` |
| theorem-search helper | TRAIL-style proof search | proof-attempt artifact source | `ProofAttemptCandidate` |
| symbolic action policy | LOA / NESTA-style policy learning | controller-candidate proposal only | `SymbolicPolicyCandidate` |

## Engine doctrine

The first implementation tranche is a catalog and contract lane only. It intentionally does not install IBM packages, PySR, Julia, theorem provers, graph stores, AMR parsers, or external model providers.

The PROMETHEUS engine registry should evolve toward:

```text
mvp_linear_fallback
optional_pysr
optional_sindy
optional_ai_descartes
optional_lnn_truth_bounds
optional_amr_logic
optional_theorem_search
```

Each optional engine must fail closed unless the runtime environment is explicitly pinned, the dataset or corpus is hashed, replay metadata exists, policy allows execution, and the output shape remains backward compatible with the PROMETHEUS candidate contract.

## Required artifact boundary

Every PROMETHEUS neuro-symbolic run artifact must carry:

- `artifactType`;
- `schemaVersion`;
- `runId`;
- `methodFamily`;
- `applicationMode`;
- dataset or corpus evidence reference;
- candidate references;
- replay hash or pending replay state;
- semantic review surface;
- promotion state;
- `controlAuthority: false`;
- non-authority declaration;
- issued timestamp.

If an artifact lacks evidence reference, replay posture, review surface, non-authority declaration, or `controlAuthority: false`, it is invalid.

## Gates

The default gates are:

1. evidence reference exists;
2. dataset or corpus hash exists where applicable;
3. replay hash exists or replay state is explicitly `pending`;
4. units status is consistent or non-applicable;
5. no governance flags;
6. no final admission requested;
7. semantic review surface is configured;
8. control authority is false;
9. candidate remains `candidate`, `proposed_for_review`, `rejected`, or `failure_corpus`.

## Non-goals

This tranche does not vendor the IBM toolkit.

This tranche does not create live execution.

This tranche does not mutate Ontogenesis.

This tranche does not create AgentPlane replay authority.

This tranche does not promote a discovered equation, rule, policy, ontology edge, or logical formula to truth.

This tranche does not add a controller path.

## Validation

Run:

```bash
python3 tools/validate_prometheus_neurosymbolic_contracts.py
```

The validator checks the PROMETHEUS-owned neuro-symbolic capability catalog and the first AI-Descartes-style / LNN-style fixture run artifacts.
