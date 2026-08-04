# Workspace Control Plane — Phase 12 (ConsensusArbitrator)

Implements **Phase 12**: the consensus arbitration layer that combines multiple
`policy_decision.v0` records from independent `PolicyGate` evaluations into a
single authoritative `consensus_decision.v0` record using a configurable quorum
rule.

## Design decisions (D20 / D21)

- **D20** — Three quorum modes cover the relevant arbitration space:
  `unanimous` (all must be `allowed`), `majority` (strict >50% must be
  `allowed`), and `any` (at least one `allowed` is sufficient).  An empty
  decision list yields verdict `blocked` — there is no quorum over nothing.
  Policies with verdict `error` count as `blocked`, preserving fail-closed
  behaviour at the arbitration layer.
- **D21** — The `ConsensusDecision` record carries the full list of
  `input_decisions` (decision_ids) so the arbitration is auditable end-to-end:
  the OTel trace shows which PolicyDecisions contributed, and the record itself
  references each one explicitly.

## Schema (consensus_decision.v0)

```python
{
  "consensus_id":     "cd-<hex12>",
  "quorum_mode":      "unanimous" | "majority" | "any",
  "verdict":          "allowed" | "blocked",
  "decided_at":       ISO-8601,
  "total":            int,          # number of decisions evaluated
  "allowed_count":    int,
  "blocked_count":    int,
  "input_decisions":  [decision_id, ...],
  "error":            null | str,
}
```

## Key classes

- **`ConsensusArbitrator(tracer, quorum_mode)`** — `arbitrate(decisions) →
  consensus_decision.v0`.  Opens a GUARDRAIL OTel span; each input decision is
  recorded as a `consensus.input` span event; result is a `consensus.decided`
  event.  Fail-closed: exceptions → verdict `blocked`, error surfaced in record
  and span.
- **`QuorumMode`** — `Literal["unanimous", "majority", "any"]`

## Quorum logic

| Mode | Passes when |
|------|-------------|
| `unanimous` | `allowed_count == total` |
| `majority` | `allowed_count > total / 2` (strict) |
| `any` | `allowed_count >= 1` |

Empty list always → `blocked`.  `error` verdicts count as `blocked`.

## Validation

`tools/tests/test_consensus_arbitrator.py` — 23 tests covering schema fields,
unique consensus_id, quorum_mode stored in record, all three quorum modes,
edge cases (empty list, single decision, all-allowed, all-blocked, exact
majority tie), error-verdict-as-blocked, counts accuracy, input_decisions
order preserved, GUARDRAIL span emitted, span attributes (quorum_mode,
input_count, verdict, allowed/blocked counts), consensus.input events per
decision, consensus.decided event, side-effect-free repeated calls.

Path-filtered CI: `.github/workflows/control-plane-phase12.yml`.

## Complete pipeline (Phases 7–12)

```
TemporalOutbox (Phase 7)          — durable run FSM
  └─ ClaimExtractor / MemoryStore (Phase 8) — evidence storage tiers
       └─ OTel Tracer (Phase 9)   — audit span tree
            └─ PolicyGate (Phase 10) — per-policy verdict + GUARDRAIL span
                 └─ EvidenceCollector (Phase 11) — full event→claim→policy loop
                      └─ ConsensusArbitrator (Phase 12) — quorum over verdicts
```

The stack is now closed: raw events enter at Phase 11, evidence accumulates at
Phase 8, policies evaluate at Phase 10, and Phase 12 arbitrates the final
workspace action authorization.
