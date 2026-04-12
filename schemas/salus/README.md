# Salus Schemas (Draft)

This directory will hold the canonical entities, events, and pathway artifacts for the Salus program.

Planned schema groups:

- patient and episode entities
- observation and media manifests
- consent and access artifacts
- pathway-state documents
- recommendation and override records
- event envelopes
- sensitivity and dignity classifications

Design posture:

- interoperable with FHIR where appropriate
- richer internal semantics than FHIR alone
- explicit provenance fields
- stable business-key identity
- replay-friendly event shapes
