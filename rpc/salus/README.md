# Salus RPC Surface (Draft)

This directory will hold TriTRPC capability contracts for the Salus program.

Initial capability families:

- `salus.patient-intake.v1`
- `salus.recommendation.v1`
- `salus.pathway-state.v1`
- `salus.policy-check.v1`
- `salus.evidence-card.v1`
- `salus.booking-route.v1`
- `salus.clinician-review.v1`
- `salus.export-governance.v1`

Each contract should define:

- request and response schemas
- actor and role requirements
- purpose-of-use constraints
- emitted events
- idempotency and replay semantics
- evidence commitments
