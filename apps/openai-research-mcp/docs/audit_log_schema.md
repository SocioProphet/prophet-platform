# Audit log schema notes

Each audit event should carry enough context to reconstruct what happened without rereading service logs.

Recommended fields:
- `ts`
- `event`
- `subject`
- `organization`
- `document_id` or `results`
- canonical `url` where relevant
- `artifact_id` for export handoff events

Do not log bearer tokens or raw secret material.
