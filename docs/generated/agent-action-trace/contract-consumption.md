# Agent Action / Trace Contract Consumption

## Purpose

This note documents the first platform-generated contract surface derived from the pinned Agent Action / Trace Conformance Profile.

## Source standards

- Runtime-facing profile: `SocioProphet/socioprophet-agent-standards#22`
- Pinned commit: `97e3f49ec4b27349f532db27ebaad618d4f9520c`
- Semantic ontology source: `SocioProphet/ontogenesis`
- Bootstrap validator source: `SocioProphet/socioprophet-standards-storage`

## Platform contract family

- `AgentActionRecord`
- `AgentTraceRecord`
- `AgentActionTraceConformanceReport`

## Initial consumers

The standards lock declares these initial platform runtime targets:

- `apps/agentplane`
- `apps/workspace-controller`
- `apps/lampstand`

Runtime-specific consumption notes:

- `docs/generated/agent-action-trace/runtime-consumption-agentplane.md`
- `docs/generated/agent-action-trace/runtime-consumption-workspace-controller.md`
- `docs/generated/agent-action-trace/runtime-consumption-lampstand.md`

## Runtime boundary

This tranche introduces generated contract artifacts only. Runtime code must not claim conformance until it emits matching records and produces a validation or receipt trail.

## Validation

Run:

```bash
python3 tools/validate_agent_action_trace_contracts.py
```
