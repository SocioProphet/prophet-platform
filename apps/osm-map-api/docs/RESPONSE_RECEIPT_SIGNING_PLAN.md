# OSM Map API Response Receipt Signing Plan

Status: v0 security plan
Owner surface: prophet-platform / osm-map-api

## Purpose

The OSM Map API currently emits unsigned service receipts that expose attribution, source refs, provenance presence, route safety status, and receipt integrity posture.

This document defines how those receipts should become cryptographically attestable without making the application server responsible for long-lived signing keys.

## Current state

`osm-map-api` emits response receipts with:

- receipt version;
- service name;
- response kind;
- source refs;
- provenance presence;
- attribution required/present state;
- attribution texts;
- license refs;
- route safety status;
- advisory safety boundary;
- unsigned integrity note.

Current receipts are transparency metadata, not cryptographic proof.

## Signing doctrine

Do not put long-lived signing keys inside `osm-map-api`.

Signing should happen at one of these controlled boundaries:

1. platform gateway / service mesh sidecar;
2. release pipeline for static fixture bundles;
3. Lattice-admitted runtime packaging pipeline;
4. evidence/attestation service once Agentplane/SocioSphere governance is wired.

The API produces canonical receipt material. A trusted boundary signs it.

## Signed receipt object

A future signed receipt should include:

```json
{
  "receipt": {},
  "canonicalization": "json-canonicalization-scheme-v1",
  "digest": "sha256:<hex>",
  "signature": {
    "type": "sigstore-bundle|dsse|jws|other",
    "bundle_ref": "...",
    "certificate_identity": "...",
    "transparency_log_ref": "..."
  },
  "verification": {
    "policy_ref": "policy://prophet-platform/osm-map-api/receipt-signing-v1",
    "verified_at": "...",
    "status": "verified|unverified|failed"
  }
}
```

## What gets signed

The signature payload must cover:

- `receipt_version`;
- `service`;
- `response_kind`;
- `source_refs`;
- `provenance_refs_present`;
- `attribution.required`;
- `attribution.present`;
- `attribution.texts`;
- `attribution.license_refs`;
- `route_safety_status`;
- `safety_boundary`;
- response artifact digest when available;
- fixture bundle or runtime release digest when available.

## What does not get signed in v0

Do not sign volatile HTTP metadata in v0:

- request ID;
- wall-clock response time;
- client IP;
- user-agent;
- transient cache headers.

Those may be handled later by gateway telemetry or OpenTelemetry traces.

## Canonicalization

Use deterministic JSON canonicalization before digesting.

Minimum rule:

- UTF-8 JSON;
- stable key order;
- no insignificant whitespace;
- arrays preserved in declared order unless explicitly sorted by producer;
- digest computed over canonical receipt object plus optional artifact digest reference.

## Signing profiles

### Profile A — Fixture release signing

Use when publishing a static fixture bundle.

Signer: release pipeline.

Covers:

- fixture bundle digest;
- generated OpenAPI contract digest;
- response receipt examples;
- attribution/source-ref policy state.

Use case:

- demo builds;
- offline verification;
- release bundles.

### Profile B — Gateway response signing

Use when serving API responses through a trusted platform gateway.

Signer: gateway or service-mesh extension.

Covers:

- receipt object;
- selected response artifact digest;
- service identity;
- deployment identity;
- policy ref.

Use case:

- production API responses;
- client-side verification;
- audit trails.

### Profile C — Lattice runtime attestation

Use after OSM runtimes are admitted to Lattice Forge.

Signer: Lattice release/runtime pipeline.

Covers:

- RuntimeAsset digest;
- SBOM digest;
- source refs;
- validation command result;
- runtime output artifact digest;
- receipt digest.

Use case:

- reproducible runtime outputs;
- provenance chain from runtime to API response.

## Verification surfaces

Receipts should be verifiable by:

- Prophet Platform gateway;
- Sherlock search records;
- GAIA world-state/evidence records;
- SocioSphere governance checks;
- Agentplane execution/evidence replay;
- Lattice Forge runtime promotion gates.

## Required future artifacts

- JSON schema for signed response receipts;
- canonicalization utility;
- digest utility;
- gateway signing integration;
- release-bundle signing integration;
- verification command;
- negative tests for missing attribution and non-advisory route status.

## Security posture

Receipt signing does not make OSM-derived routing safety-critical.

A signed receipt proves what the service claimed and what sources/provenance were presented. It does not validate road safety, route clearance, live conditions, authority approval, or HD-map correctness.

## First implementation target

The next implementation step should add:

- `schemas/osm_map_api_response_receipt.v0.schema.json`;
- a deterministic receipt digest utility;
- tests proving receipt digest stability;
- an unsigned-to-signed envelope fixture.

Actual private-key or Sigstore integration should wait until the platform-wide signing boundary is chosen.
