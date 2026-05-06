# Workspace Operation Runtime Skeleton

Status: initial runtime skeleton

Issue: SocioProphet/prophet-platform#376

## Purpose

The Workspace Operation runtime skeleton provides an early in-memory runtime for the Workspace Operation Plane. It consumes contract-shaped dictionaries from `SocioProphet/prophet-core-contracts`, applies v0.1 state-transition checks, emits immutable event dictionaries, and materializes snapshots for smoke tests and early adapter development.

This is not yet the production operation service.

## Package

```text
src/prophet_platform/workspace_operations/
```

Main entry point:

```python
from prophet_platform.workspace_operations import InMemoryOperationRuntime
```

Boundary types:

```python
from prophet_platform.workspace_operations import BoundaryResult, BoundaryDeniedError
```

Adapter registry types:

```python
from prophet_platform.workspace_operations import (
    OperationAdapterRegistry,
    StaticAdapterDeclaration,
)
```

## Current capabilities

- Create operation records.
- Attach task records.
- Load contract fixture bundles.
- Emit operation events.
- Send emitted events to an injected ledger sink.
- Materialize operation snapshots.
- Materialize operation detail for inspectors/tests.
- Validate operation state transitions.
- Validate task state transitions.
- Guard retry with `retryable=true` and non-empty idempotency key.
- Cancel operations through `canceling -> canceled` when allowed.
- Admit, quarantine, and activate artifacts with admission-state checks.
- Invoke an injected policy boundary before command-like mutations.
- Invoke an injected agent-authority boundary before actor actions.
- Register declaration-only operation adapters by operation type.
- Fail closed on duplicate or missing adapter registrations.

## Adapter registry

`OperationAdapterRegistry` is a declaration and lookup surface for operation-specific adapters. It is intentionally not a global lifecycle owner. Adapters should be thin and should return contract-shaped tasks, artifacts, decisions, policy gates, and diagnostics to the runtime.

The initial helper `StaticAdapterDeclaration` is useful for tests and early adapter wiring. It returns an `AdapterContract`-shaped declaration with operation type, supported artifact types, required capabilities, invoked policy gates, retry/idempotency behavior, emitted events, redaction rules, and fixture references.

Future real adapters should come from the appropriate repo/lane:

- upload/import: platform or storage adapter lane
- memory ingestion: `SocioProphet/memory-mesh-upstream`
- terminal command: `SourceOS-Linux/TurtleTerm`
- browser capture/download/upload: `SourceOS-Linux/BearBrowser`
- sync reconciliation: `SourceOS-Linux/sourceos-syncd`
- local agent execution: `SourceOS-Linux/agent-machine`
- release/package evidence: `SourceOS-Linux/homebrew-tap` / delivery lane
- security exercise evidence: `SocioProphet/SCOPE-D` tracked through `workspace-inventory`

## Boundaries

This runtime intentionally does not own:

- Canonical schemas.
- Policy evaluation rules.
- Ledger/evidence persistence.
- Durable storage backend.
- UI state.
- SourceOS local daemon behavior.
- Browser behavior.
- Terminal behavior.
- Agent authority.

It exposes explicit seams instead:

- `PolicyClient`: evaluates command-shaped requests and returns `BoundaryResult`.
- `LedgerSink`: records emitted runtime events as evidence.
- `AgentAuthorityHook`: authorizes actors for actions on operation resources.

Development defaults are permissive/no-op and are for smoke tests only:

- `AllowAllPolicyClient`
- `NoopLedgerSink`
- `AllowAllAgentAuthorityHook`

Production integrations must replace these with implementations backed by the appropriate control planes.

Canonical owners:

- Contracts: `SocioProphet/prophet-core-contracts`
- Policy: `SocioProphet/policy-fabric`
- Ledger/evidence: `SocioProphet/prophet-core-ledger`
- Agent authority: `SocioProphet/agentplane` and `SocioProphet/agent-registry`
- Workspace UI/controller: `SocioProphet/sociosphere`
- SourceOS local sync: `SourceOS-Linux/sourceos-syncd`

## Smoke tests

Run locally with:

```bash
PYTHONPATH=src python -m unittest discover -s tests/workspace_operations -p 'test_*.py'
```

CI workflow:

```text
.github/workflows/workspace-operation-runtime.yml
```

Current smoke coverage includes:

- operation creation and event emission
- operation transition validation
- task retry guard
- cancel path
- fixture-bundle loading
- artifact admission and activation
- policy-boundary denial
- ledger-sink event capture
- adapter registration/declaration
- duplicate adapter registration failure
- missing adapter lookup failure

## Next implementation steps

1. Add policy-client fixture adapter returning `PolicyGateRecord` shaped responses.
2. Add ledger sink fixture adapter returning operation evidence records.
3. Add command objects for the first command set.
4. Add durable persistence boundary behind the event log abstraction.
5. Add import/load path for fixtures generated by `sourceos-devtools`.
6. Add explicit worker lease/heartbeat abstractions.
7. Add adapter decomposition smoke tests with fixtures from `prophet-core-contracts`.

## Runtime rule

No operation event should be written directly by UI or agents. UI, agents, workers, local daemons, and connectors should issue validated commands. Runtime validates command, state, idempotency, policy boundary, and adapter contract before emitting events.
