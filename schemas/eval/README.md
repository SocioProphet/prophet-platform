# schemas/eval/

This directory holds canonical JSON schemas for the platform evaluation and intelligence fabric.

## Metric and context schemas

- `metric-definition.schema.json`
- `metric-fact.schema.json`
- `context-slice.schema.json`

These schemas are intentionally narrow starter anchors. They let the platform repo own the metric vocabulary and the atomic evidence model while the broader bundle continues to evolve.

## Governance and provenance schemas

- `repro-ledger-entry.schema.json` — `ReproLedgerEntry`: reproducibility ledger record linking a metric fact to its eval run, judge, and replay artifact
- `causal-attribution.schema.json` — `CausalAttribution`: causal attribution record assigning score changes to specific factors or interventions
- `methodology-snapshot.schema.json` — `MethodologySnapshot`: point-in-time snapshot of the scoring methodology used for a given eval run
- `metric-crosswalk.schema.json` — `MetricCrosswalk`: mapping between platform-internal metric identifiers and external benchmark or standard identifiers
- `judge-descriptor.schema.json` — `JudgeDescriptor`: descriptor for the judge (model, human, or hybrid) used in an eval run

Example payloads for each governance/provenance schema are in the `examples/` subdirectory.
