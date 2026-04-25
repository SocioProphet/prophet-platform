# Prophet Operations Intelligence

This document describes the first Prophet-native operations intelligence evidence slice in `prophet-platform`.

This is not an integration with proprietary observability or optimization products. It is the first open, repo-native evidence path for the same broad category of capability:

- runtime operational signals
- runtime topology evidence
- service health assessment
- policy-gated optimization recommendations

## First slice

The first slice adds four contract surfaces:

- `ProphetOperationalSignal`
- `ProphetRuntimeTopologyEvidence`
- `ProphetServiceHealthAssessment`
- `ProphetOptimizationRecommendation`

It also adds `tools/normalize_prophet_operations_evidence.py`, a vendor-neutral normalizer that accepts a compact local JSON observation and emits a `ProphetOperationsEvidenceBundle` containing normalized signals, optional topology, health assessments, and recommendations.

## Intent

The goal is to make platform operations evidence executable before building dashboards or action automation.

The minimal flow is:

```text
raw local observation
  -> normalized operational signals
  -> optional runtime topology evidence
  -> service health assessment
  -> optimization recommendation
  -> policy gate pending
```

The recommendation output is deliberately policy-gated. The helper does not execute remediation, mutate infrastructure, or grant authority. It emits evidence and proposed action intent for a later policy/evaluation layer.

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

This PR does not add:

- live collectors
- external vendor adapters
- dashboard/UI routes
- remote action execution
- scheduler mutation
- policy decision service calls

Those are follow-on slices. The correct next step is to connect recommendations to a Policy Fabric decision contract, then expose the emitted bundle through the existing platform evidence surfaces.
