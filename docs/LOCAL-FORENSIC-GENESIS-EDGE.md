# Local Forensic Genesis Edge Runtime Guide

This guide describes the **runtime/deployment** side of the Forensic Genesis edge lane.

The **normative** ADRs and value schemas live in `SocioProphet/prophet-platform-standards`.
This repository carries the local broker lane, runtime validation, and consumer-facing wiring.

## Scope
This local lane exists to prove:
- broker bring-up for edge fact topics
- optional Schema Registry bring-up for first-pass JSON Schema subjects
- publish/receipt/DLQ mechanics for edge outbox publication
- runtime validation that the expected local stack artifacts exist

## First-pass edge topics
- `edge.forensic.snmp.observed.v1`
- `edge.forensic.mounts.observed.v1`
- `edge.forensic.verify.completed.v1`
- `edge.forensic.seal.completed.v1`

## Bring-up
Use `infra/local/docker-compose.forensic-genesis-edge.yml` to start the local broker lane.

## Validation
Use `python3 tools/validate_forensic_genesis_edge.py` for repo-level validation of the local runtime surface.

## Notes
- Heavy artifacts such as PCAP should publish by manifest and digest, not inline payload.
- Edge events remain in the structural-fact lane until consumed by deeper semantic processors.
