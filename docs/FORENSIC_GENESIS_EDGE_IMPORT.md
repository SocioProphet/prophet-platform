# Forensic Genesis Edge Import Note

This repository is the runtime and deployment hub for SocioProphet. The normative standards surface for the Forensic Genesis edge lane belongs in `SocioProphet/prophet-platform-standards`.

## What belongs here
- runtime consumers of edge topics
- deployment wiring for local broker / registry lanes
- CI and smoke-test helpers for edge publication
- import and synchronization notes tying runtime code to the standards repo

## What does not belong here
- canonical topic value schemas
- normative ADRs for the edge schema family
- registry compatibility policy as a source of truth

## Initial edge topic family consumed by the platform
- `edge.forensic.snmp.observed.v1`
- `edge.forensic.mounts.observed.v1`
- `edge.forensic.verify.completed.v1`
- `edge.forensic.seal.completed.v1`

## Runtime split
The edge lane is intentionally layered:
1. host-local collection and evidence persistence
2. outbox publisher into Kafka fact topics
3. compacted latest-state materializations where useful
4. optional routing into deeper semantic/control-flow lanes

## Immediate runtime tasks
- add a local Redpanda/Schema Registry bring-up lane under `infra/local/`
- add runtime consumers for the edge fact topics
- add smoke tests proving publish/receipt/DLQ behavior on a real broker
- bind runtime contracts back to the standards repo pins
