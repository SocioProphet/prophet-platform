# Sovereign Device Orchestration Contracts

Status: initial canonical contract slice
Parent strategy: `docs/strategy/sovereign-device-orchestration.md`

This directory defines the fixture-backed contract layer for the sovereign device orchestration tranche. It is intentionally vendor-neutral. Apple Home, Google Home/Gemini, Samsung SmartThings, Amazon Alexa, Home Assistant, Matter/Thread, browsers, shells, wearables, vehicles, local agents, and cloud services are normalized into the same governed objects.

## Contract objects

The first slice uses six canonical objects:

1. `DeviceNode` — a governed node in the human/device/home/browser/shell/agent/cloud graph.
2. `AdapterState` — the health, operating mode, and credential boundary of an ecosystem adapter.
3. `OrchestrationEvent` — an observed or inferred event from a device, routine, assistant, agent, policy, or sync path.
4. `Routine` — an inspectable automation object compiled from natural language, UI, or code into a signed representation.
5. `PolicyDecision` — a Guardrail Fabric decision that allows, denies, redacts, degrades, or requires approval.
6. `EvidenceReceipt` — the durable receipt emitted for every perception, proposal, approval, denial, actuation, override, repair, and sync export.

## Files

- `orchestration_contract_fixture.py` — stdlib-only fixture generator and validator for the canonical bundle and all six object families.
- `embodied_experience_trace_fixture.py` — E2WM-style embodied trace generator and validator for track/count, permanence, plan generation, and policy-aware planning.
- `event_capability_fixture.py` — event bus, subscription, capability, reaction, idempotency, dead-letter, replay, and evidence fixture.
- `world_class_event_loop_demo.py` — end-to-end fixture proof that projects the current contracts into policy-annotated records, SourceOS queue state, AgentPlane admission, Sherlock index, and a demo report.

## Validation

Run `python specs/orchestration/orchestration_contract_fixture.py` to validate the core fixture bundle. Run `python specs/orchestration/orchestration_contract_fixture.py --json` to emit the canonical JSON bundle.

Run `python specs/orchestration/embodied_experience_trace_fixture.py` to validate embodied trace fixtures. Run `python specs/orchestration/embodied_experience_trace_fixture.py --records` to emit train/eval records.

Run `python specs/orchestration/event_capability_fixture.py` to validate event-capability fixtures. Run `python specs/orchestration/event_capability_fixture.py --events` to emit flattened records.

Run the world-class event loop proof:

`python specs/orchestration/world_class_event_loop_demo.py`

The demo writes artifacts under `artifacts/orchestration/world-class-event-loop/` by default:

- `core-orchestration.bundle.json`
- `embodied-traces.bundle.json`
- `embodied-training-records.json`
- `event-capability.bundle.json`
- `event-capability.records.json`
- `event-capability.policy-annotated.records.json`
- `sourceos-queue.snapshot.json`
- `agentplane-admission.artifact.json`
- `sherlock-event-capability-index.json`
- `demo-report.json`

The proof passes only when core contracts, embodied traces, event capabilities, policy annotation, queue projection, AgentPlane admission, and Sherlock indexing all satisfy the world-class invariants.

## Design constraints

Natural language may propose routines, but natural language is not the executable source of truth. Executable routines must be inspectable, versioned, diffable, testable, signed, revocable, and auditable.

Agents may observe, explain, search, draft, and propose. Physical or high-risk digital actuation must pass through capability checks, Guardrail Fabric policy, approval mode, and evidence receipt emission.

No first-slice contract requires live Apple, Google, Samsung, Amazon, or Home Assistant credentials. Live adapters must conform to these shapes after fixture validation is stable.

## First demo path

1. Fixture/Home Assistant adapter emits device nodes and events.
2. SourceOS `sourceos-syncd` records local receipts and preserves replay/idempotency semantics.
3. Ontogenesis validates schemas and ontology mappings.
4. Guardrail Fabric evaluates policy decisions.
5. AgentPlane gates agent-proposed action.
6. Sherlock Search indexes receipts and answers evidence-backed questions.
7. SocioProphet UI renders the device graph, timeline, routine proposal, adapter health, and evidence drawer.

## Event-native target

The event-native target is:

`event -> subscription -> capability -> policy -> admission -> approval if needed -> guarded execution -> receipt -> replay/dead-letter/search`

The bootstrap demo remains non-mutating. It does not actuate devices, call providers, collect credentials, or retain camera media. It proves state, policy, evidence, replay, and search before any runtime actuation is allowed.
