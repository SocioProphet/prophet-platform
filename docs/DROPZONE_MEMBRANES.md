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
- `apps/cell-service` emits governed Personal Intelligence Cell signal/feed/publication records
- a future zone router should enforce publication policy before Kafka/topic emission

## Personal Intelligence Cell membrane alignment

Personal Intelligence Cell publication must cross a New Hope-style membrane before it reaches slash topics, Sherlock Search packets, or external feed channels.

The first mapping is:

- policy `allow` -> membrane **admit**
- policy `deny` -> membrane **reject**
- policy `quarantine` -> membrane **quarantine**
- policy `review_required` -> membrane **hold**
- policy `redact` -> membrane **hold**

The required lineage across this membrane is:

```text
cellRef + sourceRef + watchRef + signalRef + feedItemRef + evidenceRefs + policyDecision
```

The corresponding service-local builder is `new_hope_membrane_event` in `apps/cell-service/src/cell_service/publication.py`.

## Contract alignment

This membrane layer should converge on imported `new-hope` carrier and membrane semantics, with event/surface envelopes aligned to imported `semantic-serdes` contracts.
