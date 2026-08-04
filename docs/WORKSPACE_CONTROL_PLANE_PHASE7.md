# Workspace Control Plane — Phase 7 (temporal outbox + approvals)

Implements **Phase 7**: a durable outbox and approval gate for external
side-effects, scaffold-first. The Temporal.io **semantics** — append-only
event log, compensation on failure, and an explicit D12 approval gate —
are implemented in-process with **no Temporal cluster dependency**; the
real Temporal infra swaps in behind the same `TemporalOutbox` interface later.

## Design decisions (D11 / D12)

- **D11** — External side effects run through durable workflows. Every
  mutation is logged to an in-memory append-only event log; `replay()`
  reconstructs the current state from that log.
- **D12** — Approval gates are fail-closed. A run that has transitioned to
  `awaiting_approval` **cannot** reach `succeeded` without an explicit
  `approve()` call from an identity in the `authorized_approvers` list.
  Any other identity — including the original actor — is refused at the gate.

## State machines

```
Run status:
  pending → running → awaiting_approval → running → succeeded
                                        → compensated
            running → succeeded
            running → failed
            running → compensated
  (succeeded / failed / compensated are terminal)

Outbox state:
  none → queued → sent → acked          (happy path)
  queued / sent → failed → queued       (retry, up to OUTBOX_MAX_RETRIES)
  failed → compensated                  (after max retries)
```

## Key classes

- **`WorkflowRun`** — in-memory projection of `workflow-run.v0`. Call
  `to_contract()` to emit the schema-conformant dict; `from_contract()` to
  round-trip.
- **`TemporalOutbox`** — the durable outbox engine. Public API:
  `create / start / request_approval / approve / complete / fail / compensate /
  advance_outbox / replay / event_log`.
- **`InvalidTransitionError`** — raised on any disallowed state-machine step.
- **`ApprovalRequiredError`** — raised if `complete()` is called on a run
  that is still `awaiting_approval` (D12 fail-closed).
- **`MaxRetriesExceededError`** — raised when `advance_outbox(to_state="queued")`
  is called after `OUTBOX_MAX_RETRIES` attempts have been exhausted.

## Validation

`tools/tests/test_temporal_outbox.py` — 15 tests covering the happy path,
D12 approval gate (4 negative cases proving the gate bites), outbox state
machine (queued→sent→acked, retry, max-retries), invalid transitions,
compensation, event-log / replay, and schema conformance against the
frozen `workflow-run.v0` contract.

Path-filtered CI: `.github/workflows/control-plane-phase7.yml`.

## Next (Phase 8)

Claim extraction + memory tiers (Letta/Graphiti/GraphRAG/HippoRAG) over
the `claim.v0` and `evidence.v0` schemas already frozen in Phase 1.
