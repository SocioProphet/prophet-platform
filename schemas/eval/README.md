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

## Submission validity and public surfaces (MLPerf / Zenodo parity)

- `submission.schema.json` + `division-rules.json` — the submission descriptor and the OPEN/CLOSED division rules (#1271). `tools/validate_submission.py` composes the estate gates into ONE pass/fail verdict per division.
- `leaderboard-round.schema.json` — `LeaderboardRound`: a versioned, ranked-or-tiered public round FOR ONE division (#1272). `tools/publish_leaderboard_round.py` publishes a round only when EVERY entry's submission passes `validate_submission`; OPEN rounds are flagged non-comparable. An entry may reference a `RecipeProof` (#1296) and a DOI (#1267).
- `oais-deposition.schema.json` — `OaisDeposition`: the OAIS preservation/curation vault package chain SIP→AIP→DIP (#1272). `tools/oais_deposition.py` verifies SHA-256 fixity (FIPS 180-4 algorithm), PREMIS-shaped preservation metadata, an OAI-PMH (`oai_dc`) record, and that the DIP fixity matches the AIP. An accepted submission produces a citable, DOI-ready AIP (#1267).

Examples: `examples/leaderboard-round.closed.example.json`, `examples/oais-deposition.example.json` (+ `examples/oais-content/`). Gate: `make validate-eval-surfaces` / `.github/workflows/eval-surfaces-gate.yml`.
