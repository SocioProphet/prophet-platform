# Observability — OpenTelemetry + OpenInference Semantic Conventions

**Version:** 0.1 — Pre-Implementation Design
**Status:** DRAFT — FOR REVIEW
**Custodian:** M.D. Heller / SocioProphet
**Scope:** prophet-platform (eval-fabric-api and other AI-operating services) · Workspace-Control-Plane gap D15
**Companion specs:** `docs/PLATFORM_TELEMETRY_REQUIREMENTS.md`, `docs/CHANNEL_GOVERNED_RUNTIME_GATES.md`, `docs/CANONICAL_COMPONENT_MAP.md`, `telemetry/README.md`, `contracts/EvidenceReceipt.v0.1.json`, `adr/ADR-033-canonical-receipts-and-event-envelopes.md`

---

## 1. Purpose and Scope

This document defines the **OpenInference span conventions** for AI operations in
`prophet-platform`, and the **collector substrate** (OpenTelemetry) that carries
them. It closes the platform-wide observability gap **Workspace-Control-Plane
D15** and realizes the "Adopt now … OTel+OpenInference (P3)" line item in
`docs/CANONICAL_COMPONENT_MAP.md`.

It is **additive**. It does not replace the existing transparent-telemetry seed
(`telemetry/`), the reasoning-evidence fabric (ReasoningRun / Event / Receipt /
ReplayPlan), or the channel/autonomy gates. It binds to them.

### The core distinction (do not collapse it)

> **Spans are the live trace. Receipts are the durable evidence.**

OTel spans give us low-latency, sampled, in-flight visibility into a request as
it moves through discovery → retrieval → planning → tool-calls → gates → side
effects. They are *operational*. They may be sampled, dropped, or expire.

The **reasoning-evidence fabric** (`app/receipts.py`,
`contracts/EvidenceReceipt.v0.1.json`) is the *durable, hash-chained record* —
the system of record per `docs/CANONICAL_COMPONENT_MAP.md`. It is never sampled
away. Spans **do not replace receipts**; they reference them.

The two are joined by one key.

---

## 2. The correlation key: reasoning-run id

Every span carries a **trace context that correlates to a ReasoningRun /
Receipt** in the evidence fabric. The join key is the existing evidence-fabric
field **`correlation_id`** (present on the envelope, the event, and
`EvidenceReceipt`). In span-space we surface it as:

| Span attribute              | Meaning                                                        |
|-----------------------------|----------------------------------------------------------------|
| `prophet.reasoning_run.id`  | == `correlation_id` of the ReasoningRun / EvidenceReceipt      |
| `prophet.receipt.ref`       | Optional `receipt://<id>` pointer to the durable receipt        |
| `prophet.service.ref`       | Producing service, e.g. `apps/eval-fabric-api`                  |
| `openinference.span.kind`   | One of the six span kinds in §3                                |

**Binding rule:** a service opens a span with `prophet.reasoning_run.id = R`,
does its work, then emits the receipt with `correlation_id = R`. Span and receipt
now line up by id. The tracing seam (`app/tracing.py`) yields `R` so the same
value flows into `receipts.emit_artifacts(correlation_id=R)` automatically.

Standard OTel `trace_id` / `span_id` still apply (see
`docs/PLATFORM_TELEMETRY_REQUIREMENTS.md`); `prophet.reasoning_run.id` is the
*business* correlation that ties the OTel trace to durable evidence.

---

## 3. Span kinds for AI operations

Each AI operation is one **OpenInference span kind**. Required attributes are
listed; all spans additionally carry the §2 correlation attributes. Attribute
values must respect plane field-class rules from `telemetry/` — in particular,
**no raw prompt text, raw assistant text, file names, or content snippets** on
spans destined for analytics planes (use hashes/refs instead).

| Span kind     | `openinference.span.kind` | Fires when…                                              | Required attributes                                                                 |
|---------------|---------------------------|---------------------------------------------------------|------------------------------------------------------------------------------------|
| Discovery     | `discovery`               | the system searches/enumerates candidate sources/tools  | `prophet.query.hash`, `discovery.candidate_count`                                  |
| Retrieval     | `retrieval`               | evidence/context is fetched for grounding               | `prophet.query.hash`, `retrieval.result_count`, `retrieval.source_refs` (refs only)|
| Planning      | `planning`                | a plan / decomposition / route is selected              | `planning.strategy`, `planning.step_count`                                         |
| Tool-call     | `tool_call`               | an external tool / model / function is invoked          | `tool.name`, `tool.input_hash`, `tool.output_hash`                                 |
| Approval/gate | `approval`                | a channel or autonomy gate evaluates the action         | `gate.class`, `gate.decision`, `gate.policy_decision_id`, `autonomy.level`         |
| Side-effect   | `side_effect`             | a consequential sink is written (memory/graph/publish/exec) | `sink.kind`, `sink.decision`, `prophet.receipt.ref`                            |

Notes:
- **Retrieval `source_refs`** are content-addressable refs (e.g. `evidence://…`),
  never raw documents.
- **Tool-call** `*_hash` follow the same digest convention as `receipts.digest_json`.
- **Approval/gate** maps directly to the gate classes in
  `docs/CHANNEL_GOVERNED_RUNTIME_GATES.md` (`ingest_gate`, `collapse_gate`,
  `memory_sink_gate`, `graph_sink_gate`, `projection_sink_gate`, `action_sink_gate`)
  and to the L0–L5 autonomy ladder. See §5.
- **Side-effect** spans SHOULD carry `prophet.receipt.ref` because a consequential
  sink MUST also produce a durable receipt — the span is just its live shadow.

A typical AI request produces a span tree:
`discovery → retrieval → planning → (tool_call)* → approval → side_effect`,
all sharing one `prophet.reasoning_run.id`, with the durable receipt(s) carrying
the same `correlation_id`.

---

## 4. The collector substrate

`infra/local/docker-compose.otel-collector.yml` + `infra/local/otel-collector/config.yaml`
run a local OTel Collector (OTLP gRPC :4317 / HTTP :4318). Kustomize equivalents
live at `infra/k8s/otel-collector/{base,overlays/p0-lab}`.

Default pipelines are **backend-free** (a `debug` exporter) so the collector runs
locally with no dependencies. The Prometheus and Loki exporters are
**placeholders** marked `NEEDS-REAL-ENDPOINT`; wire them when those backends exist.

---

## 5. How spans relate to the autonomy / channel gates

The `approval` span kind is where observability meets governance:

- When a channel-governed gate guards a high-consequence sink for an `L4`
  conductor-orchestrated action, the platform emits an **AutonomyAdmissionReceipt**
  (`contracts/AutonomyAdmissionReceipt.v0.1.json`). The corresponding `approval`
  span carries `gate.policy_decision_id` and `autonomy.level` so the live trace
  shows *why* the action was admitted or blocked.
- The `side_effect` span fires only after the `approval` span's
  `gate.decision == allow`. A `side_effect` span with no preceding allowed
  `approval` span in the same `reasoning_run` is an **observable governance
  violation** — a property worth alerting on.
- Spans never *make* gate decisions; they *report* them. The gate logic and its
  durable receipts remain authoritative.

---

## 6. Non-goals

- Spans do not become the system of record. (Receipts are.)
- The seam does not change plane semantics, retention, or field-class rules in
  `telemetry/`.
- No real metrics/log backend is mandated here; only the substrate to receive them.
