# Reasoning Failure Runner v0.1

Parent: SocioProphet/sociosphere#271 and SocioProphet/prophet-platform#405.

This slice adds the first runtime-facing reasoning-failure runner contract. The initial implementation is deliberately narrow: exact-string verification over synthetic fixtures only.

## Purpose

The runner converts a standards-shaped reasoning-failure case and perturbation suite into a provider-neutral `ReasoningFailureReceipt`. The receipt can later be consumed by Guardrail Fabric, Policy Fabric, AgentPlane, Model Governance Ledger, Agent Registry, Model Router, Sherlock, and DeliveryExcellence.

## Initial deterministic lane

The first lane targets exactness failures. It compares a protected string with an observed string and emits a failed receipt when they are not byte-identical.

This covers high-risk operational surfaces such as:

- config keys;
- release refs;
- schema refs;
- package names;
- filenames;
- checksums;
- exact IDs;
- boot/runtime identifiers.

## Non-goals

This slice does not call external models, run LLM-as-judge, execute tools, mutate state, write ledger records, change guardrail behavior, or route agents. It creates deterministic synthetic evidence that downstream repos can consume.

## CLI target

```bash
python3 tools/emit_reasoning_failure_receipt.py \
  --case examples/reasoning-failure/exact-string-case.json \
  --suite examples/reasoning-failure/exactness-perturbation-suite.json \
  --out build/reasoning-failure/exact-string-receipt.json
```

## Safety posture

The fixture uses `synthetic-only` privacy posture. Raw customer data, secrets, browser profiles, token stores, private app databases, regulated data, and unredacted telemetry are out of scope for this runner slice.
