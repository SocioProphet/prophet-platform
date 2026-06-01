# Workspace Controller Agent Action / Trace Consumption Note

## Purpose

This note defines the first consumption boundary for the workspace-controller surface against the generated Agent Action / Trace contracts.

## Expected future role

The workspace controller should eventually preserve or reference action/trace records when workspace orchestration requests trigger governed agent-plane work.

## Current boundary

This note is documentation-only. It does not claim workspace-controller runtime conformance.

## Required future evidence

A future implementation PR should show:

- action records associated with workspace operation requests
- trace records for coordination outcomes
- references to policy decisions and receipts
- no direct treatment of traces as execution authority

## Authority split

Workspace state and orchestration context remain separate from semantic ontology authority and from policy authorization.
