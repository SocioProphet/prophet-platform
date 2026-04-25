# Prophet Operations Intelligence

This document describes the first Prophet-native operations intelligence evidence slice in `prophet-platform`.

This is not an integration with proprietary observability or optimization products. It is the first open, repo-native evidence path for the same broad category of capability:

- runtime operational signals
- runtime topology evidence
- service health assessment
- policy-gated optimization recommendations
- evidence links to governed Policy Fabric action decisions

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

Those are follow-on slices. The correct next step is to expose the emitted operations bundle through existing platform evidence surfaces and add a policy-decision ingest/example path once Policy Fabric decisions are produced by a live evaluator.
