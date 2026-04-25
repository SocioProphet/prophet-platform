# Prophet Operations Intelligence

This document describes the first Prophet-native operations intelligence evidence slice in `prophet-platform`.

This is not an integration with proprietary observability or optimization products. It is the first open, repo-native evidence path for the same broad category of capability:

- runtime operational signals
- runtime topology evidence
- service health assessment
- policy-gated optimization recommendations
- evidence links to governed Policy Fabric action decisions
- local validation that blocks execution unless a matching allow decision exists

## First slice

The first slice adds four contract surfaces:

- `ProphetOperationalSignal`
- `ProphetRuntimeTopologyEvidence`
- `ProphetServiceHealthAssessment`
- `ProphetOptimizationRecommendation`

It also adds `tools/normalize_prophet_operations_evidence.py`, a vendor-neutral normalizer that accepts a compact local JSON observation and emits a `ProphetOperationsEvidenceBundle` containing normalized signals, optional topology, health assessments, recommendations, and evidence links.

## Intent

The goal is to make platform operations evidence executable before building dashboards or action automation.

The minimal flow is:

```text
raw local observation
  -> normalized operational signals
  -> optional runtime topology evidence
  -> service health assessment
  -> optimization recommendation
  -> Policy Fabric action decision reference
  -> evidence link
  -> local decision validation
  -> executable only when decision.outcome=allow
```

The recommendation output is deliberately policy-gated. The helper does not execute remediation, mutate infrastructure, or grant authority. It emits evidence and proposed action intent for a later policy/evaluation layer.

## Policy Fabric decision linkage

Each non-healthy assessment can emit a `ProphetOptimizationRecommendation`. Each recommendation carries:

- `policy_gate.required=true`
- `policy_gate.policy_ref=policy://operations/default-action-gates/v1`
- `policy_gate.decision_contract_ref=schema://policy-fabric/contracts/prophet_operations_action_decision_v1.schema.json`
- `policy_gate.decision_ref=policy-fabric://prophet-operations-action-decision/v1/<recommendation_id>`
- `policy_gate.decision=pending`

The decision contract lives in `SocioProphet/policy-fabric` as `ProphetOperationsActionDecision`. The platform-side bundle does not make the decision. It records the required decision target and emits an evidence link that connects the operations bundle to the policy-decision artifact.

The emitted evidence-link shape is:

```json
{
  "kind": "ProphetOperationsEvidenceLink",
  "schema_version": "v0.1",
  "from_ref": "artifact://prophet-platform/operations/<bundle_id>",
  "to_ref": "policy-fabric://prophet-operations-action-decision/v1/<recommendation_id>",
  "relationship": "requires_policy_decision",
  "contract_ref": "schema://policy-fabric/contracts/prophet_operations_action_decision_v1.schema.json",
  "recommendation_ref": "<recommendation_id>"
}
```

A checked-in example is available at:

- `examples/operations/prophet_operations_evidence_bundle_with_policy_decision_links_0001.json`

## Action decision enforcement

`tools/validate_prophet_operations_policy_decisions.py` validates operations bundles against supplied `ProphetOperationsActionDecision` artifacts.

Execution rule:

- missing decision: blocked
- `decision.outcome=pending`: blocked
- `decision.outcome=manual_review`: blocked
- `decision.outcome=defer`: blocked
- `decision.outcome=deny`: blocked
- `decision.outcome=unknown`: blocked
- `decision.outcome=allow`: executable only if recommendation, subject, and action linkage match

The validator also checks that the decision uses:

- `kind=ProphetOperationsActionDecision`
- `schema_version=v1`
- `recommendation_ref=<recommendation_id>`
- matching `subject.id` and `subject.type`, when present
- matching `proposed_action.type` and `proposed_action.intent`, when present

Example blocked validation:

```bash
python tools/validate_prophet_operations_policy_decisions.py \
  --bundle examples/operations/prophet_operations_evidence_bundle_with_policy_decision_links_0001.json \
  --decision examples/operations/prophet_operations_action_decision_manual_review_0001.json
```

Example executable validation:

```bash
python tools/validate_prophet_operations_policy_decisions.py \
  --bundle examples/operations/prophet_operations_evidence_bundle_with_policy_decision_links_0001.json \
  --decision examples/operations/prophet_operations_action_decision_allow_0001.json \
  --require-executable
```

Checked-in decision examples:

- `examples/operations/prophet_operations_action_decision_manual_review_0001.json`
- `examples/operations/prophet_operations_action_decision_allow_0001.json`

## Input shape

The normalizer accepts JSON with these optional top-level fields:

- `source`
- `observed_at`
- `signals`
- `topology`

Example:

```json
{
  "source": {"system": "local-demo", "emitter": "unit-test"},
  "observed_at": "2026-04-25T18:00:00Z",
  "signals": [
    {
      "subject": {"id": "svc-api", "type": "service", "name": "api"},
      "signal": {"name": "error_rate", "type": "metric", "value": 0.12, "unit": "ratio", "severity": "warn"}
    }
  ],
  "topology": {
    "scope": {"environment": "test"},
    "nodes": [{"id": "svc-api", "type": "service", "name": "api"}],
    "edges": []
  }
}
```

Run:

```bash
python tools/normalize_prophet_operations_evidence.py raw.json --output artifacts/operations/bundle.json
```

## Deliberate limits

This lane does not add:

- live collectors
- external vendor adapters
- dashboard/UI routes
- remote action execution
- scheduler mutation
- live policy service calls

Those are follow-on slices. The current enforcement surface is local: it proves that an operation recommendation cannot be treated as executable unless a supplied Policy Fabric decision artifact explicitly allows it and links to the recommendation consistently.
