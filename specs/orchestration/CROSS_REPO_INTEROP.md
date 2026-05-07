# Cross-Repo Event Loop Interop Proof

Status: executable runbook

This is the cross-repo proof path for sovereign, event-native device orchestration. The target is not another smart-home routine system. The target is a governed event membrane where every observation, proposal, policy decision, queue transition, admission result, search hit, and replay artifact is typed, idempotent, evidence-backed, and non-mutating until explicitly admitted.

## Repos in the proof

- `SocioProphet/prophet-platform` emits canonical contracts, event-capability records, world-model traces, and the aggregated demo report.
- `SocioProphet/guardrail-fabric` turns event-capability records into generated policy outcomes.
- `SourceOS-Linux/sourceos-syncd` persists event-capability records into a local-first queue with pending, waiting-approval, blocked, dead-letter, replay, and audit paths.
- `SocioProphet/agentplane` admits, blocks, or waits on records before execution.
- `SocioProphet/sherlock-search` indexes event-capability records as evidence-backed search packets.

## Local directory convention

Assume repos live under `~/dev`.

```bash
export DEV_ROOT="$HOME/dev"
export SDO_OUT="/tmp/sdo-world-class-event-loop"
export ORCH_ROOT="/tmp/sourceos-syncd-orchestration"
```

## 1. Generate canonical Prophet Platform artifacts

```bash
cd "$DEV_ROOT/prophet-platform"
python specs/orchestration/orchestration_contract_fixture.py
python specs/orchestration/embodied_experience_trace_fixture.py
python specs/orchestration/event_capability_fixture.py
python specs/orchestration/world_class_event_loop_demo.py --out "$SDO_OUT" --compact
jq '.status, .summary' "$SDO_OUT/demo-report.json"
```

Expected: `status` is `pass`.

## 2. Generate Guardrail Fabric policy outcomes

```bash
cd "$DEV_ROOT/guardrail-fabric"
python -m pip install -e .
guardrail-fabric-event-capability \
  --input "$SDO_OUT/event-capability.records.json" \
  --out "$SDO_OUT/event-capability.guardrail-annotated.records.json"
```

Expected: the annotated records contain policy decisions with `allowed`, `requires_approval`, `denied`, and `redacted` outcomes where appropriate.

## 3. Queue records in SourceOS

```bash
cd "$DEV_ROOT/sourceos-syncd"
python -m pip install -e .
sourceos-syncd orchestration init --root "$ORCH_ROOT" --compact
sourceos-syncd orchestration enqueue \
  --root "$ORCH_ROOT" \
  --file "$SDO_OUT/event-capability.guardrail-annotated.records.json" \
  --compact > "$SDO_OUT/sourceos-enqueue.json"
sourceos-syncd orchestration summary --root "$ORCH_ROOT" --compact > "$SDO_OUT/sourceos-summary.json"
sourceos-syncd orchestration list --root "$ORCH_ROOT" --state pending --compact > "$SDO_OUT/sourceos-pending.json"
sourceos-syncd orchestration list --root "$ORCH_ROOT" --state waiting-approval --compact > "$SDO_OUT/sourceos-waiting-approval.json"
sourceos-syncd orchestration list --root "$ORCH_ROOT" --state blocked --compact > "$SDO_OUT/sourceos-blocked.json"
sourceos-syncd orchestration replay --root "$ORCH_ROOT" --state pending --compact > "$SDO_OUT/sourceos-replay-pending.json"
```

Expected queue shape:

- low-risk fan reaction appears in `pending`
- high-risk security reaction appears in `waiting-approval`
- camera media release appears in `blocked`
- replay artifact is non-mutating

## 4. Validate AgentPlane admission

```bash
cd "$DEV_ROOT/agentplane"
python scripts/validate_event_capability_admission.py \
  --input "$SDO_OUT/event-capability.guardrail-annotated.records.json" \
  --out "$SDO_OUT/agentplane-admission.artifact.json"
jq '.summary, .agentMayExecute' "$SDO_OUT/agentplane-admission.artifact.json"
```

Expected: no invalid records. Some records may be blocked or waiting for approval. Strict mode is intentionally not used for the bootstrap proof because the proof includes blocked and approval-required events.

## 5. Search the event stream in Sherlock

```bash
cd "$DEV_ROOT/sherlock-search"
python tools/search_event_capability_records.py \
  --index "$SDO_OUT/event-capability.guardrail-annotated.records.json" \
  --query "security approval" \
  --out "$SDO_OUT/sherlock-security-approval.search.json"
python tools/search_event_capability_records.py \
  --index "$SDO_OUT/event-capability.guardrail-annotated.records.json" \
  --query "camera media denied" \
  --out "$SDO_OUT/sherlock-camera-denied.search.json"
python tools/search_event_capability_records.py \
  --index "$SDO_OUT/event-capability.guardrail-annotated.records.json" \
  --query "fan allowed temperature" \
  --out "$SDO_OUT/sherlock-fan-allowed.search.json"
```

Expected: search results preserve event id, capability id, reaction id, policy outcome, idempotency key, policy epoch, and receipt refs.

## 6. Cross-repo pass criteria

The interop proof is passing when all of the following are true:

1. Prophet Platform `demo-report.json.status == pass`.
2. Guardrail Fabric produces policy-annotated records from unannotated event-capability records.
3. SourceOS queue shows at least one pending, one waiting-approval, and one blocked record.
4. SourceOS replay emits a non-mutating replay artifact.
5. AgentPlane admission has zero invalid records.
6. Sherlock search returns evidence-backed hits with event, capability, reaction, policy, idempotency, and receipt fields.
7. No live device actuation, provider call, credential collection, or camera media retention occurs.

## Why this is world class

The important product distinction is not voice control or routine chaining. The distinction is governed event causality.

This proof establishes:

- event-native semantics instead of opaque automations
- exactly-once behavior by idempotency key
- dead-letter and replay paths before live actuation
- explicit policy-generation boundary
- AgentPlane admission gate before execution
- searchable evidence fields for Sherlock
- embodied trace compatibility for world-model evaluation
- fixture-first operation with no proprietary ecosystem dependency

Runtime actuation can only be added after this membrane remains stable under CI and cross-repo smoke tests.
