# Lampstand Agent Action / Trace Consumption Note

## Purpose

This note defines the first consumption boundary for Lampstand against the generated Agent Action / Trace contracts.

## Expected future role

Lampstand should eventually index action/trace records and conformance reports so users and agents can search governed coordination evidence.

## Current boundary

This note is documentation-only. It does not claim Lampstand runtime conformance.

## Required future evidence

A future implementation PR should show:

- indexed action record references
- indexed trace record references
- search/result surfaces that identify policy and receipt refs
- no promotion of trace records into authorization authority

## Indexing rule

Lampstand may index traces as evidence and retrieval context. It must not become the authority for deciding whether an action was allowed.
