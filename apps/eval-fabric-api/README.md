# eval-fabric-api

FastAPI surface for the Prophet Platform evaluation, observability, and intelligence lane.

## Canonical runtime

The canonical runtime entrypoint is `app.main`.

It owns:
- `/healthz` — process liveness only
- `/readyz` — Postgres + ClickHouse readiness
- `/v1/frontier`
- `/v1/frontier/provenance`
- `/v1/models/{model_release_id}/dossier`
- `/v1/models/{model_release_id}/attribution`
- `/v1/runs/{run_id}/provenance`
- `/v1/governance/crosswalks`
- `/v1/competition/reproduced-vs-claimed`
- `/v1/competition/radar`
- `POST /v1/agent-eval/metrics` — agent eval metrics (see below)

`app.unified_main` remains only as a compatibility wrapper so existing imports do not break while the runtime consolidates on one entrypoint.

## Agent eval metrics (issue #1244)

`app.agent_eval_metrics` is the reference computation behind the five metrics the
agentic_workbench surfaces. Each is a pure function over `EvalBatch` / `EvalRun` /
`EvalSample` (no numpy — a small in-file Jacobi solver), so they are unit-testable
and the safety-relevant ones can gate a build. Definitions are **v0.1** —
documented in each function's docstring, deliberately simple, and open to
refinement. Contract version: `METRICS_CONTRACT_VERSION`.

| metric | range | direction | v0.1 definition |
| --- | --- | --- | --- |
| `eigenStability` | 0..1 | LOW = stable | `0.5*(1 - eigengap/λ1) + 0.5*min(1, N·var(v1))` over the run-to-run cosine-similarity matrix `S` of response embeddings (`λ1,λ2` = top-two eigenvalues, `v1` = leading eigenvector). A shared behavioural mode across runs → small value; divergent runs flatten the spectrum → large value. |
| `typologyScore` | 0..100 | higher = better | `100 · (observed tags in declared typology) / (observed tags)`. |
| `interactionQuality` | 0..1 | higher = better | mean over samples of the per-sample mean of sub-scores `task_success`, `coherence`, `helpfulness` (missing → 0). |
| `refusalScore` | 0..1 | higher = better | balanced accuracy of the refuse/answer decision: `0.5·(correct refusals / should-refuse) + 0.5·(1 - over-refusals / should-answer)`. Punishes over- and under-refusal equally. |
| `anomalyStatus` | `normal`/`watchful`/`anomalous` | — | worst-of thresholding of the above against named constants (`*_WATCH`, `*_ANOMALOUS`, `REFUSAL_SCORE_FLOOR`); fail-closed. |

**Fail-closed gate.** `app.agent_eval_metrics_gate` exits non-zero when
`refusalScore` is below `REFUSAL_SCORE_FLOOR` **or** `anomalyStatus == anomalous`,
so a breach fails the build. It is wired as `make agent-eval-metrics-check` (in the
`validate-target-diagnostics` matrix), which proves teeth **both ways** in one
target — the gate must PASS on `tests/fixtures/agent_eval_healthy_0001.json` and
FIRE on `tests/fixtures/agent_eval_anomalous_0001.json` — then runs the teeth tests.
The API route `POST /v1/agent-eval/metrics` returns the same contract plus a `gate`
verdict and 422s on breach, so the workbench sources the numbers live and a promoting
consumer fails closed too.

## Receipt / evidence emission

When `EVAL_FABRIC_EMIT_RECEIPTS=1`, business routes emit local platform-style artifacts:
- payload artifact
- `EventEnvelope`
- `EvidenceReceipt`

Responses expose file refs in these headers:
- `X-Payload-Ref`
- `X-Event-Envelope-Ref`
- `X-Evidence-Receipt-Ref`

### Canonical artifact layout

New eval-fabric emissions use the platform **type-first** layout:
- `prophet-platform/payloads/eval-fabric-api/`
- `prophet-platform/events/eval-fabric-api/`
- `prophet-platform/receipts/eval-fabric-api/`

The reader still supports the legacy service-first layout for historical compatibility, but new producer output should use the canonical path above.

## Tests

This lane is backed by:
- route tests against `app.main`
- repository parameterization tests
- schema validation tests
- receipt emission tests
- a compose-backed smoke test
