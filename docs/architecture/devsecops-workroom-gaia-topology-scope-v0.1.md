# DevSecOps Workroom GAIA Topology Scope v0.1

Status: Workstream 5 scope closure  
Plane: Prophet Platform Workroom consumption of GAIA topology/blast-radius evidence  
Related: `docs/architecture/devsecops-intelligence-workroom-v0.1.md`

## Purpose

This note closes the v0.1 scope for GAIA topology and blast-radius integration in the DevSecOps Intelligence Workroom.

GAIA topology integration is v0.1-scoped to post-merge incident investigation.

Pre-merge validation topology is deferred to a later tranche because it requires tighter alignment with the active Signadot-parity runtime lane, especially changed-service routing, baseline fallback, HTTP/gRPC isolation, async isolation, stateful resources, teardown, and leak-check evidence.

## v0.1 included scope

The v0.1 integration covers:

- post-merge incident Workroom records;
- `topology://gaia/workroom/...` references;
- `blast-radius://gaia/workroom/...` references;
- topology snapshot evidence;
- candidate affected service nodes;
- candidate consumer nodes;
- topology-supported blast-radius hypotheses.

Current fixture path:

```text
fixtures/external/gaia/workroom-post-merge-topology.valid.json
```

Current validator:

```text
tools/validate_workroom_gaia_topology_refs.py
```

## v0.1 excluded scope

The v0.1 integration does not cover:

- pre-merge sandbox topology;
- changed-service route graph;
- baseline fallback graph;
- HTTP/gRPC request-routing proof;
- async queue/topic isolation topology;
- stateful resource isolation topology;
- teardown/TTL topology;
- leak-check topology;
- customer impact confirmation.

These exclusions are intentional. They prevent GAIA topology from outrunning AgentPlane/Sociosphere runtime evidence.

## Claim boundary

Allowed v0.1 claim:

```text
GAIA topology supports post-merge Workroom dependency context and candidate blast-radius hypotheses.
```

Forbidden v0.1 claims:

```text
GAIA topology proves RCA causality.
GAIA topology confirms customer impact.
GAIA topology authorizes remediation.
GAIA topology certifies Signadot-style feature parity.
GAIA topology proves pre-merge sandbox routing or isolation.
```

## Required validation posture

A valid Workroom-to-GAIA reference must preserve:

- Workroom `source_refs.topology_ref` equals GAIA `topology_ref`;
- Workroom `source_refs.blast_radius_ref` equals GAIA `blast_radius_ref`;
- Workroom topology evidence appears in GAIA `source_evidence`;
- Workroom topology evidence provenance points to the topology ref;
- GAIA `radius_status` remains `candidate_only` or `supported_by_topology` unless observational impact evidence exists;
- Workroom RCA claims are not upgraded to `confirmed_causal_claim` from topology alone;
- Workroom remediation plans are not `executed` from topology evidence.

## Deferred pre-merge topology tranche

A later pre-merge GAIA topology tranche should define:

- sandbox topology refs;
- changed-service and baseline topology snapshots;
- route-isolation evidence refs;
- async/stateful isolation refs;
- teardown/leak-check topology refs;
- merge-readiness blast-radius posture.

That tranche must depend on the runtime parity lane rather than replacing it.

## Non-claims

This note does not execute runtime probes.

This note does not validate live topology.

This note does not certify RCA causality.

This note does not authorize remediation.

This note does not certify Signadot feature parity.
