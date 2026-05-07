# World-Class Event Loop Proof Dossier

Status: fixture-backed, CI-gated proof spine

This dossier records the current proof state for sovereign, event-native orchestration. It exists to prevent the work from dissolving into repo-local fragments. The proof standard is a governed event membrane where every observation, proposal, policy decision, queue transition, admission result, search hit, replay artifact, and UI rendering is typed, idempotent, evidence-backed, and non-mutating until explicitly admitted.

## One-line thesis

Apple owns continuity, Google is advancing AI home inference, Samsung owns appliance graph depth, and Home Assistant owns local-first control. Our differentiator is governed event causality across all of them.

## Canonical event loop

```text
event
  -> subscription
  -> capability
  -> policy
  -> reaction
  -> SourceOS queue
  -> AgentPlane admission
  -> Sherlock index
  -> SocioProphet workbench
```

## Proof artifacts by repo

### SocioProphet/prophet-platform

Canonical owner for contracts, fixture generation, and the aggregated proof.

Implemented artifacts:

- `docs/strategy/sovereign-device-orchestration.md`
- `specs/orchestration/orchestration_contract_fixture.py`
- `specs/orchestration/embodied_experience_trace_fixture.py`
- `specs/orchestration/event_capability_fixture.py`
- `specs/orchestration/world_class_event_loop_demo.py`
- `specs/orchestration/CROSS_REPO_INTEROP.md`
- `.github/workflows/ci.yml` orchestration fixture job

Proof command:

```bash
python specs/orchestration/world_class_event_loop_demo.py --out /tmp/world-class-event-loop --compact
jq '.status, .summary' /tmp/world-class-event-loop/demo-report.json
```

Pass condition: `demo-report.json.status == pass`.

### SocioProphet/guardrail-fabric

Canonical owner for deterministic policy generation.

Implemented artifacts:

- `guardrail_fabric/device_orchestration_policy.py`
- `guardrail_fabric/event_capability_policy.py`
- `guardrail_fabric/event_capability_cli.py`
- `tests/test_device_orchestration_policy.py`
- `tests/test_event_capability_policy.py`
- `pyproject.toml` entry point: `guardrail-fabric-event-capability`

Proof command:

```bash
guardrail-fabric-event-capability \
  --input /tmp/world-class-event-loop/event-capability.records.json \
  --out /tmp/world-class-event-loop/event-capability.guardrail-annotated.records.json
```

Pass condition: records have generated policy decisions and no high-risk direct allow.

### SourceOS-Linux/sourceos-syncd

Canonical owner for local-first queue, idempotency, dead-letter, replay, and audit semantics.

Implemented artifacts:

- `src/sourceos_syncd/orchestration_events.py`
- `examples/orchestration/event-capability.records.json`
- `tests/test_orchestration_events.py`
- `.github/workflows/ci.yml` orchestration queue exercise

Proof command:

```bash
sourceos-syncd orchestration init --root /tmp/sourceos-syncd-orchestration --compact
sourceos-syncd orchestration enqueue \
  --root /tmp/sourceos-syncd-orchestration \
  --file /tmp/world-class-event-loop/event-capability.guardrail-annotated.records.json \
  --compact
sourceos-syncd orchestration replay --root /tmp/sourceos-syncd-orchestration --state pending --compact
```

Pass condition: at least one pending, one waiting-approval, and one blocked record; replay is non-mutating.

### SocioProphet/agentplane

Canonical owner for admission before execution.

Implemented artifacts pending merge:

- PR #130: `Add event capability admission gate`
- `scripts/validate_event_capability_admission.py`
- `examples/orchestration/event-capability.records.json`
- `docs/integration/event-capability-admission.md`

Observed status:

- PR #130 remains open.
- Head workflow runs observed as successful for `ci`, `lint`, and `validate`.
- Direct merge through the connector was rejected by branch protection despite visible lint success.

Proof command after merge or local branch checkout:

```bash
python scripts/validate_event_capability_admission.py \
  --input /tmp/world-class-event-loop/event-capability.guardrail-annotated.records.json \
  --out /tmp/world-class-event-loop/agentplane-admission.artifact.json
```

Pass condition: zero invalid records. Blocked and waiting-for-approval records are expected in non-strict bootstrap mode.

### SocioProphet/sherlock-search

Canonical owner for evidence search.

Implemented artifacts:

- `tools/search_event_capability_records.py`
- `tools/smoke_event_capability_records_search.py`
- `.github/workflows/event-capability-record-search.yml`

Proof command:

```bash
python tools/search_event_capability_records.py \
  --index /tmp/world-class-event-loop/event-capability.guardrail-annotated.records.json \
  --query "security approval" \
  --out /tmp/world-class-event-loop/sherlock-security-approval.search.json
```

Pass condition: search results preserve event id, capability id, reaction id, policy outcome, idempotency key, policy epoch, receipt refs, and evidence refs.

### SocioProphet/socioprophet

Canonical public surface and integration workbench.

Implemented artifacts:

- `docs/orchestration/event-workbench.md`
- `docs/guide/event-native-orchestration-workbench.md`
- `marketing/public/orchestration/index.html`
- `marketing/public/orchestration/event-native-fixture.json`
- `scripts/build_event_orchestration_fixture.py`
- `scripts/smoke_build_event_orchestration_fixture.py`
- `scripts/verify_event_orchestration_workbench.py`
- `.github/workflows/event-orchestration-workbench.yml`

Proof command:

```bash
python scripts/smoke_build_event_orchestration_fixture.py
python scripts/verify_event_orchestration_workbench.py
```

Pass condition: fixture, builder, page, docs, and navigation all verify; the page remains read-only and non-mutating.

## World-class invariants

The current proof spine enforces or documents the following invariants:

1. Every reaction has an idempotency key.
2. Every reaction has receipt references.
3. Every high-risk action is approval-required or denied.
4. Camera media release is denied by default in the first slice.
5. SourceOS queue state is partitioned into pending, waiting-approval, blocked, and dead-letter.
6. Replay is non-mutating.
7. AgentPlane admission has zero invalid records before execution can proceed.
8. Sherlock search preserves event, capability, reaction, policy, idempotency, epoch, and receipt fields.
9. The public workbench is read-only and fixture-backed.
10. No live device actuation, provider call, credential collection, or camera-media retention occurs in the bootstrap proof.

## Current proof state

```text
Strategy and contract spine      : complete enough for bootstrap
E2WM trace layer                  : fixture-backed and validated
Event-capability contract         : fixture-backed and CI-gated
Guardrail policy generation       : implemented with tests
SourceOS queue/replay             : implemented with tests and CI exercise
AgentPlane admission              : implemented in PR #130; merge blocked
Sherlock event search             : implemented with CI smoke
SocioProphet workbench            : implemented as read-only fixture surface with CI smoke
Cross-repo interop                : runbook exists; one full manual pass still needed
Live actuation                    : intentionally not implemented
```

## Definition of done for bootstrap

Bootstrap is done when:

- `prophet-platform` orchestration fixture CI passes.
- `guardrail-fabric` event-capability policy tests pass.
- `sourceos-syncd` orchestration event tests and CI exercise pass.
- AgentPlane PR #130 is merged or an equivalent admission gate lands.
- `sherlock-search` event-capability search smoke passes.
- `socioprophet` workbench verifier passes.
- `CROSS_REPO_INTEROP.md` has been executed once and evidence artifacts are retained.

## Definition of done for first bounded-live tranche

Bounded-live work can begin only after bootstrap is done. First bounded-live tranche requires:

- one non-sensitive adapter source, preferably fixture-compatible Home Assistant or SourceOS-local events;
- signed or hash-stable receipt emission;
- no camera-media retention;
- no live actuation except low-risk, explicit test-only targets;
- replay/dead-letter coverage;
- UI data mode banner set to `bounded-live`;
- operator-visible rollback or no-op mode.

## Remaining risks

- AgentPlane PR #130 branch protection must be resolved.
- Cross-repo command chain has not yet been executed by a single automation.
- Fixture records and public UI fixture can drift unless generated regularly from Prophet Platform demo artifacts.
- Runtime actuation must not be added before admission, replay, and evidence are stable.

## Next move

Resolve AgentPlane PR #130, then execute `CROSS_REPO_INTEROP.md` end to end and attach the resulting artifact paths to issue #445.
