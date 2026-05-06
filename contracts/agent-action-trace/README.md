# Agent Action / Trace Contracts

This directory contains generated platform-facing contract artifacts derived from the pinned `agent-action-trace-profile` standards import in `standards.lock.yaml`.

## Upstream authority

- Normative runtime-facing profile: `SocioProphet/socioprophet-agent-standards`
- Semantic ontology authority: `SocioProphet/ontogenesis`
- Bootstrap examples and validator authority: `SocioProphet/socioprophet-standards-storage`

## Current artifacts

- `agent-action-record.v0.1.schema.json`
- `agent-trace-record.v0.1.schema.json`
- `agent-action-trace-conformance-report.v0.1.schema.json`
- valid examples under `examples/`
- invalid examples under `examples/invalid/`

## Validation

Run:

```bash
python3 tools/validate_agent_action_trace_contracts.py
```

The validator checks positive examples and asserts the negative fixtures fail as expected.

## Negative fixtures

The negative fixture set currently proves rejection of:

- an `AgentActionRecord` missing `receiptRef`
- an `AgentTraceRecord` that incorrectly sets `traceIsAuthority: true`
- an `AgentActionTraceConformanceReport` that points bootstrap-validator authority at the wrong repository

## Boundary

These contracts do not implement runtime behavior. They define the platform-generated contract surface that downstream runtime components can consume in later implementation PRs.
