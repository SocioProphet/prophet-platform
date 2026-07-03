# Reasoning Task Evaluation Fabric v0.1

## Purpose

This note turns the reasoning-workbook taxonomy, Masonmark governed intent-to-contract compilation, Practical Statistical Relational AI, UReQA / ARC reasoning requirements, external-knowledge NLI, and KR R2K query-rewriting work into an executable test surface for `prophet-platform`.

The fixture set is deliberately small. Its purpose is not to become the final benchmark. Its purpose is to establish the contract: every reasoning family we absorb must have a stable task id, explicit verifier, expected answer status, logic/probability binding, and receipt requirements.

## Source abstractions absorbed

The reasoning workbook contributes bounded symbolic and spatial task families: numeric series, alphabet series, coding/decoding, symbolic operator substitution, constraint puzzles, Venn/set relations, clock/calendar reasoning, cube/dice reasoning, visual transformations, and non-verbal analogy/classification.

Masonmark contributes the governed compiler pattern: natural language must compile into typed executable meaning, with schema grounding, AST or logical form, verifier state, read-only policy, execution trace, replay hash, proofpack, and promotion/abstention state.

Practical Statistical Relational AI contributes the logic/probability bridge: weighted first-order rules, Markov logic, MAP/marginal inference targets, lifted or lazy grounding, weighted satisfiability, and probabilistic relational model bindings.

UReQA / ARC and KR R2K contribute the complex QA pipeline: characterize question knowledge/reasoning requirements, rewrite queries using essential terms and background knowledge, retrieve passages, run entailment or QA resolvers, aggregate answer evidence with decision rules, and route weak evidence to review.

The external-knowledge NLI work contributes a defeasible commonsense bridge: knowledge graphs such as ConceptNet can help textual entailment, but their contribution must remain explicit, traceable, and overridable. They are support, not institutional truth.

## Evaluation contract

Every fixture must include:

- `task_id`;
- `task_family`;
- `verifier`;
- `answer_status`;
- `input`;
- `expected_answer`;
- `reasoning_operations`;
- `logic_probability_binding`.

Every future run should emit receipt fields:

- `task_id`;
- `task_family`;
- `verifier`;
- `answer_status`;
- `model_answer`;
- `expected_answer`;
- `solver_trace_ref`;
- `logic_probability_binding_ref`;
- `evidence_ref`.

## Implemented fixture classes

The first executable checker validates these families:

1. arithmetic progression completion;
2. affine recurrence wrong-term detection;
3. Caesar-style letter coding;
4. reverse-alphabet numeric coding;
5. symbolic mathematical operator substitution;
6. underdetermined constraint recognition;
7. Masonmark SQL AST execution over tiny fixture databases;
8. Masonmark logical-form execution over a tiny KB;
9. Markov-logic soft-rule fixture shape;
10. ARC-style query rewriting using essential terms;
11. entailment resolver top-k answer selection;
12. external-knowledge NLI bridge requirements;
13. QA-as-entailment hypothesis splitting;
14. abstention under low evidence;
15. knowledge/reasoning annotation taxonomy validation;
16. Masonmark proofpack minimum field validation;
17. schema-grounded dual-IR validation.

## Architectural landing map

`prophet-platform` owns this executable checker, fixture pack, Makefile target, and future evidence receipt emission.

`ontogenesis` should own the durable ontology terms for `ReasoningTask`, `ComplexQATask`, `QueryRewriteTask`, `EntailmentResolverTask`, `ExternalKnowledgeNLITask`, `MasonmarkProofpack`, `SchemaIR`, `ProgramIR`, `AnswerStatus`, and `DefeasibleSupport`.

`agentplane` should own solver routing: deterministic in-process checks, SQL/DSL execution, external entailment models, graph-augmented NLI, MLN/PSL/ILP solvers, and human-review escalation.

`semantic-serdes` should own exchange schemas once these fixtures need cross-repo portability.

Sherlock / search should index task ids, task families, verifier types, evidence refs, answer-status labels, grounding candidates, rejected candidates, and replay digests.

## Governance rule

A model output is not trusted merely because it is fluent, syntactically valid, or high-confidence. It must either pass the task verifier and emit a complete receipt, or preserve an explicit abstention / review state.

## Promotion path

1. Keep v0.1 as deterministic fixture validation.
2. Add generated variants for each family.
3. Emit JSON evidence receipts for each run.
4. Connect AgentPlane solver routing.
5. Promote ontology terms into `ontogenesis`.
6. Add Sherlock indexing and regression replay.
7. Graduate stable families into model-evaluation gates.
