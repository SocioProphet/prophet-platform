# Complies with Standards — Multi-Domain Geospatial Intelligence

Status: Draft implementation conformance

This implementation repository consumes the SocioProphet multi-domain geospatial standards package.

## Standards consumed

- `SocioProphet/prophet-platform-standards/docs/standards/070-multidomain-geospatial-standards-alignment.md`
- `SocioProphet/prophet-platform-standards/registry/multidomain-geospatial-standards-map.v1.json`
- `SocioProphet/socioprophet-standards-storage/docs/standards/096-multidomain-geospatial-storage-contracts.md`
- `SocioProphet/socioprophet-standards-knowledge/docs/standards/080-multidomain-geospatial-knowledge-context.md`
- `SocioProphet/socioprophet-agent-standards/docs/standards/020-multidomain-geospatial-agent-runtime.md`

## Implementation responsibility

`prophet-platform` owns product requirements, API surfaces, control surfaces, acceptance criteria, and runtime-boundary requirements for standards-compliant geospatial capabilities.

It MUST NOT define stable data, knowledge, or runtime contracts independently of the standards repos. It MAY define implementation requirements and acceptance tests that reference those standards.

## Required platform surfaces

- map and tile API requirements
- routing and advisory status requirements
- OSM / ESRI / OGC / Google Maps / Google Earth parity acceptance criteria
- multi-domain geospatial dashboard/control-surface requirements
- standards conformance status reporting
- runtime-boundary visibility
- governance status visibility

## Promotion gate

A platform capability may move from draft to stable only when it references the standards map and the relevant storage, knowledge, and agent standards.
