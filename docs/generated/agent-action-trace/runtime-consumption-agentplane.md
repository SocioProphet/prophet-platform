# AgentPlane Agent Action / Trace Consumption Note

## Purpose

This note defines the first consumption boundary for AgentPlane against the generated Agent Action / Trace contracts.

## Expected future role

AgentPlane should eventually emit or preserve:

- `AgentActionRecord`
- `AgentTraceRecord`
- `AgentActionTraceConformanceReport`

## Current boundary

This note is documentation-only. It does not claim AgentPlane runtime conformance.

## Required future evidence

A future AgentPlane implementation PR should include:

- at least one emitted `AgentActionRecord` fixture
- at least one emitted `AgentTraceRecord` fixture
- a conformance report fixture
- linkage to policy decision and receipt references
- validator execution evidence using `tools/validate_agent_action_trace_contracts.py`

## Non-authority rule

AgentPlane must treat traces as coordination/evidence artifacts, not as authorization.
