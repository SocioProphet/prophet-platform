# Workspace Control Plane — Phase 9 (OTel / OpenInference observability)

Implements **Phase 9**: an OpenTelemetry / OpenInference observability scaffold
over workspace workflow-run and claim events — structured spans, typed attributes,
evidence traces, and policy decision records — with **no opentelemetry-sdk
dependency**. Swap the real OTel SDK behind the same `Tracer` / `SpanExporter`
interfaces when the infra is ready; the semantic conventions and span contract
do not change.

## Design decisions (D14 / D15)

- **D14** — Every state transition in `TemporalOutbox` emits a span. Approval
  decisions carry `approval.approver`, `approval.decision`, and
  `approval.authorized` as typed attributes, not free-form log strings.
  Unauthorized approvers produce a span with `approval.authorized=False` before
  raising `InvalidTransitionError` — the denial is always recorded in the trace.
- **D15** — Every `MemoryStore` ingest and recall operation emits a span tagged
  with the tier (T1/T2/T3/T4), subject, query, and result count. `recall_similar`
  spans include the query text and the returned `claim_id` list so the retrieval
  path is fully auditable.

## Semantic conventions

Follows OpenTelemetry Trace API + OpenInference v0.0.8 + Prophet Platform
extensions:

| Namespace       | Keys                                                         |
|-----------------|--------------------------------------------------------------|
| `workflow.*`    | `run_id`, `status.before`, `status.after`, `outbox_state`   |
| `approval.*`    | `approver`, `decision`, `authorized`                         |
| `claim.*`       | `claim_id`, `subject`, `epistemic_level`, `confidence`, `method`, `contradiction_status` |
| `memory.*`      | `tier`, `result_count`, `query`, `subject`, `term`           |
| `openinference.*` | `span.kind`, `input.value`, `output.value`, `retrieval.documents` |

Span kinds used: `CHAIN` (workflow ops), `RETRIEVER` (memory recall),
`TOOL` (memory ingest), `GUARDRAIL` (approval gate).

## Key classes

- **`Span`** — immutable after `finish()`; raises `RuntimeError` on post-close
  mutation. Carries `span_id`, `trace_id`, `parent_span_id`, `attributes`,
  `events`, `status` (ok|error|unset), `duration_ms`.
- **`SpanEvent`** — timestamped annotation with structured attributes (e.g.
  `run.created`, `approval.denied`).
- **`Tracer`** — `start_span(name, *, parent_span, attributes)` + `span()`
  context manager (auto-finishes, sets `status=error` on exception).
- **`InMemoryExporter`** — thread-safe; use in tests.
- **`JSONLinesExporter`** — appends one JSON line per span to a file.
- **`instrument_outbox(outbox, tracer)`** — non-invasive runtime patch of
  `TemporalOutbox` (create/start/complete/fail/approve).
- **`instrument_memory(store, tracer)`** — non-invasive runtime patch of
  `MemoryStore` (ingest/recall_recent/recall_by_subject/recall_similar/recall_by_term).

## Validation

`tools/tests/test_otel_tracer.py` — 29 tests covering span structure, unique
IDs, parent-child linking, immutability, exporter thread safety, JSONLines format,
context manager error semantics, span events, workflow transition spans,
authorized/unauthorized approval spans, all four memory recall tiers, trace chain
integrity, and duration non-negativity.

Path-filtered CI: `.github/workflows/control-plane-phase9.yml`.

## Next (Phase 10)

Policy fabric integration: emit `PolicyDecision` records as spans
(`openinference.span.kind=GUARDRAIL`) whenever a governance gate fires, with
structured evidence refs (`evidence.ref[]`) linking to the claim corpus.
