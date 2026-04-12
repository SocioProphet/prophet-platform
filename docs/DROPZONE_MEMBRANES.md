# Dropzone Membranes

This document defines the first dropzone membrane outline for `prophet-platform`.

## Purpose

A dropzone is not just an upload folder. It is a policy-bound ingress membrane.

## Minimal membrane outcomes

- **admit**: event may proceed into the next zone/topic lane
- **quarantine**: hold for safety or policy review
- **reject**: deny entry and emit a rejection receipt
- **hold**: retain locally until additional context or approval exists

## Relation to existing apps

- `apps/lampstand` remains the local-daemon indexing and receipt-emission lane
- `apps/knowledge-reason` remains the governed claim-evaluation ingress scaffold
- a future zone router should enforce publication policy before Kafka/topic emission

## Contract alignment

This membrane layer should converge on imported `new-hope` carrier and membrane semantics, with event/surface envelopes aligned to imported `semantic-serdes` contracts.
