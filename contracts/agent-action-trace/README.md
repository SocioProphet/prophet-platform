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
- `examples/agent-action-record.example.v0.1.json`
- `examples/agent-trace-record.example.v0.1.json`
- `examples/agent-action-trace-conformance-report.example.v0.1.json`

## Validation

Run:

```bash
python3 tools/validate_agent_action_trace_contracts.py
```

## Boundary

These contracts do not implement runtime behavior. They define the platform-generated contract surface that downstream runtime components can consume in later implementation PRs.
