# Fog Stack external signature verification inputs

This document defines the normalization contract for ingesting external signature verification outputs.

## Goal

Provide a stable input format so different tools (cosign, sigstore, etc.) can feed into the Fog Stack trust pipeline.

## Minimal flow

1. run external verification (e.g. `cosign verify`)
2. capture JSON output
3. run `tools/normalize_fogstack_signature_verification_evidence.py`
4. feed normalized output into cryptographic verification record emitter

## Why this matters

Without normalization, every tool produces different JSON, making the trust pipeline brittle.

This step standardizes input before it becomes part of the Fog Stack trust graph.

## Out of scope

- actual verification execution
- trust enforcement
- CI automation
