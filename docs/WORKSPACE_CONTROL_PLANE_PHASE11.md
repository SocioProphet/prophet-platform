# Workspace Control Plane — Phase 11 (evidence ingestion pipeline)

Implements **Phase 11**: the evidence ingestion pipeline that closes the loop
from raw event sources to governance verdicts — fetch → extract → ingest →
evaluate — all wired through the OTel span tree built in Phase 9.

## Design decisions (D18 / D19)

- **D18** — The collector is stateless between runs: each tick fetches events
  from the source since `last_collected_at`, extracts claims, ingests into the
  store, and returns a `CollectionReport`. No persistent state is required in
  the scaffold; add a `StateStore` adapter when needed.
- **D19** — Policies are evaluated immediately after each collection tick so
  the governance verdict is always fresh: new evidence can clear a previous
  `blocked` verdict or introduce a new one. The report carries both the ingested
  claim count and the policy decisions for full auditability.

## Pipeline stages

```
EventSource.fetch()
    → ClaimExtractor.extract()   (per event, above min_text_length noise gate)
    → MemoryStore.ingest()       (per claim, fail-soft: ValueError → ingest_errors++)
    → PolicyGate.evaluate()      (per policy, always after ingest)
    → CollectionReport
```

Every stage is a child OTel span of the `evidence.collect` CHAIN root:
- `evidence.fetch` — TOOL span, attributes: events_fetched
- `evidence.extract` — TOOL span per event, attributes: source_id, event_type, claim_count
- `evidence.evaluate.{policy_id}` — CHAIN span per policy wrapping GUARDRAIL sub-spans

## Key classes

- **`Event`** — `source_id`, `text`, `event_type`, `timestamp`.
- **`EventSource`** — base; override `fetch(since)`. Built-in adapters:
  - `InMemoryEventSource` — push/drain; use in tests and integration.
  - `StaticTextSource` — fixed list, yields once (useful for backfill).
- **`CollectionReport`** — `report_id`, `collected_at`, `events_fetched`,
  `claims_extracted`, `claims_ingested`, `ingest_errors`, `policy_decisions`,
  `span_trace_id`, `error`.
- **`EvidenceCollector`** — `collect() → CollectionReport`. Fail-soft: any
  exception → `report.error` set, never crashes the caller.
- **Scheduler** (scaffold) — `schedule(interval_s)` / `cancel()` using
  `threading.Timer`; swap for APScheduler/Temporal when infra is ready.

## Validation

`tools/tests/test_evidence_collector.py` — 18 tests covering report schema,
unique report IDs, InMemoryEventSource drain, incremental fetch (second tick
only sees new events), StaticTextSource yields-once semantics, claim ingestion
into store, report count consistency, claim recall after collect, noise gate
(short events skipped), allowed/blocked policy verdicts, multi-policy evaluation,
OTel trace_id in report, CHAIN root span, fetch/extract child spans, fail-soft on
broken source, and scheduler start/cancel smoke.

Path-filtered CI: `.github/workflows/control-plane-phase11.yml`.

## Next (Phase 12)

Consensus arbitration: when two policies disagree (one `allowed`, one `blocked`),
a `ConsensusArbitrator` applies a configurable quorum rule (e.g. majority vote,
unanimous required) over the set of active `PolicyGate` evaluations and emits a
final `ConsensusDecision` record — the last layer before a workspace action is
authorized.
