# zone-router

This app is the initial runtime lane for zone-aware publication and policy-gated routing.

## Intended responsibilities

- resolve zone-scoped topic targets
- validate publication preconditions before emission
- preserve envelope and receipt lineage across zone crossings
- provide a narrow runtime seam for Kafka/topic publication

## First-slice scope

This directory is intentionally documentation-first in the initial PR. Runtime implementation should follow after imported contract mirrors are pinned and validated.
