# Reasoning Failure Runner v0.1

## Purpose

`apps/reasoning-failure-runner` is the first narrow runtime slice for issue #405. It records a synthetic reasoning-failure case, runs deterministic perturbation checks, and emits a provider-neutral `ReasoningFailureReceipt v0.1`.

This follows the same lifecycle-boundary discipline used across AgentPlane, Guardrail Fabric, Agent Registry, and Model Governance Ledger:

```text
case + perturbation suite = evidence input
reasoning-failure runner = deterministic verifier lane
ReasoningFailureReceipt = evidence receipt
downstream consumers = separate follow-on planes
```

## Boundary

This runner does not use an LLM judge.

It does not call Guardrail Fabric, mutate Agent Registry authority, write Model Governance Ledger records, admit AgentPlane execution, or index Sherlock records directly.

It emits a receipt with downstream refs only.

## Initial fixture family

The first fixture is an exact-string case:

```text
apps/reasoning-failure-runner/examples/exact-string-case.json
apps/reasoning-failure-runner/examples/exactness-perturbations.json
```

The deterministic verifier checks whether `candidateOutput` exactly matches `expected.exactString`. This catches filename/checksum/string-exactness failures without using LLM-only judgment.

## CLI

```bash
PYTHONPATH=apps/reasoning-failure-runner/src \
python3 -m reasoning_failure_runner.cli run \
  --case apps/reasoning-failure-runner/examples/exact-string-case.json \
  --suite apps/reasoning-failure-runner/examples/exactness-perturbations.json \
  --out build/reasoning-failure-runner/reasoning-failure-receipt.json
```

## Validation

```bash
python3 tools/validate_reasoning_failure_receipt.py build/reasoning-failure-runner/reasoning-failure-receipt.json
```

Or run the focused smoke:

```bash
python3 tools/smoke_reasoning_failure_runner.py
```

## Receipt fields

The receipt includes:

```text
case_id
case_type
suite_id
perturbation_ids
data_boundary
provider_dependency
llm_judge_used
deterministic_verifier_refs
verifier_results
invariant_outcomes
policy_decision
residual_risk
mitigation_suggestions
next_action
evidence_refs
downstream_refs
receipt_hash
```

## Acceptance posture for #405

This tranche satisfies the first functional path:

- synthetic exact-string case in;
- perturbation suite in;
- deterministic verifier hook executed;
- provider-neutral receipt out;
- no LLM-only judgment;
- no raw regulated/customer/personal data;
- downstream consumer refs only.

Later tranches can add relation reversal, identifier swap, unsupported causal claim, temporal inconsistency, multimodal contradiction via fixture refs, and multi-agent premature termination families behind the same receipt contract.
