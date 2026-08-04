# Workspace Control Plane — Phase 10 (policy gate + PolicyDecision records)

Implements **Phase 10**: a policy gate that evaluates named policies against
the memory store and emits `PolicyDecision` records as GUARDRAIL-kind OTel
spans — with structured evidence refs linking each verdict back to the claim
corpus built in Phase 8.

## Design decisions (D16 / D17)

- **D16** — Policy decisions are full provenance records. Every verdict carries
  the `policy_id`, the `claim_id`s that triggered or cleared each rule, and the
  evaluation timestamp. Audit trail is in the span tree: the GUARDRAIL span
  wraps the memory recall spans that produced the evidence, so a Phoenix/Arize
  viewer shows the full chain: gate fired → rules → evidence claims.
- **D17** — Gate composition: policies are lists of named `Rule` objects each
  with a `require_term` (min count of matching claims) and an optional
  `forbid_term` (any match blocks). Combined verdict: `allowed` only when all
  `require` rules pass AND no `forbid` rules fire. Fail-closed: exceptions
  during evaluation yield `blocked`.

## PolicyDecision schema (policy_decision.v0)

```json
{
  "decision_id":   "pd-<hex12>",
  "policy_id":     "string",
  "verdict":       "allowed | blocked | error",
  "evaluated_at":  "ISO-8601",
  "rules": [
    {
      "rule_name":   "string",
      "passed":      true,
      "match_count": 3,
      "evidence":    ["claim-abc", "claim-def"]
    }
  ],
  "evidence_refs": ["claim-abc", "claim-def"],
  "error":         null
}
```

## Key classes

- **`Rule`** — `name`, `require_term`, `min_count` (default 1), `forbid_term`
  (optional). Require pass: `recall_by_term(require_term)` returns ≥ `min_count`
  claims. Forbid block: any match on `forbid_term` overrides.
- **`Policy`** — `policy_id`, ordered list of `Rule` objects.
- **`PolicyGate`** — `evaluate(policy) → policy_decision.v0 dict`. Opens a
  GUARDRAIL OTel span for the whole evaluation. Each rule's recall is a child
  RETRIEVER span, creating a full trace: `policy.evaluate.{id}` →
  `policy.rule.{name}.require` / `.forbid`.
- Fail-closed: any exception → `verdict=blocked`, `error` populated.
- Evidence deduplication: `evidence_refs` contains no duplicate `claim_id`s.

## Validation

`tools/tests/test_policy_gate.py` — 20 tests covering schema fields, unique
`decision_id`, allowed/blocked verdicts, vacuous empty policy, `min_count`
semantics, forbid term blocking, multi-rule all-or-nothing gate, rule result
fields, evidence refs deduplication, GUARDRAIL span emission, verdict attribute,
RETRIEVER child spans per rule, trace chain (child → parent), fail-closed
exception → blocked, and span emitted even on error.

Path-filtered CI: `.github/workflows/control-plane-phase10.yml`.

## Next (Phase 11)

Evidence ingestion pipeline: a scheduled `EvidenceCollector` that reads from
an external source (git log, CI events, audit trail), extracts claims via
`ClaimExtractor`, ingests into `MemoryStore`, and triggers `PolicyGate`
evaluations — closing the loop from raw evidence to governance verdicts.
