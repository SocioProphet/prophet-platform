# Fog Stack status and roadmap

This document captures the current state of Fog Stack work inside `prophet-platform`.

## Repository role

`prophet-platform` is the runtime and deployment substrate for platform services. Fog Stack lands here as the productization, conformance, release, publication, and trust layer for deployable offerings built on that substrate.

## Repository strategy decision

Fog Stack should **not** split into separate repositories for AI, Data, Automation, Security, or other future pack categories yet.

At the current stage, the trust/release/publication machinery is still highly shared across all surfaces. Splitting now would mostly increase coordination overhead and fragment the release/trust graph before those categories have clearly independent lifecycles.

The correct near-term move is:
- keep the engineering and trust/release/publication machinery in `prophet-platform`
- track future pack categories here as product surfaces and readiness states
- split into separate repos only when a pack has an independently justified lifecycle, release cadence, operator surface, and support burden

See also:
- `docs/FOGSTACK_PACKS.md`
- `catalog/fogstack-packs-v0.1.yaml`

## Merged offering slices

The following initial offering slices are already merged into `main`:

- **Fog Stack Access** — initial upstream offering slice via PR #25
- **Fog Stack Knowledge** — governed ingress + local daemon offering slice via PR #26
- **Fog Stack Evaluation** — evaluation fabric offering slice via PR #27
- **Fog Stack Office / Collaboration** — office collaboration runtime schema and service slice via PRs #314–#319
- **Fog Stack Data / GovernAI** — Lattice Studio/Data/GovernAI product-surface fixtures (product-spine, annotation-to-training, active metadata, trust/reputation, runtime profile catalog, demo readiness report, runtime release readiness) via PRs #299–#308
- **Fog Stack AI / Lattice Studio** — Lattice Studio AI product-surface fixtures (model zoo, prompt/RAG/eval lab, publication review, runtime profile catalog, demo readiness report, runtime release readiness) via PRs #299–#308

## Merged validation and release-engineering slices

The following supporting slices are already merged into `main`:

- native validator/helper surfaces and initial Access bundle/rulepack
- release metadata refresh via PR #41
- release schemas and validation execution criteria via PR #42
- CI-oriented validation-record emitter via PR #48
- native `Makefile` validation hook refresh via PR #51
- signed-manifest attachment helper via PR #52
- signed-manifest verification helper via PR #58
- signature trust evidence record via PR #62
- release evidence index via PR #63
- artifact backlinking via PR #68
- cryptographic signature verification record via PR #76
- external signature verification input normalization via PR #93
- external signature verification runner via PR #134
- release sealing via PR #136
- release seal signature support via PR #143
- release seal cryptographic verification record via PR #148
- release seal verification runner via PR #151
- release seal artifact linking via PR #153
- release proof pipeline runner via PR #159
- release proof CI workflow via PR #160
- wider release graph linking via PR #161 and refreshed follow-up PR #165
- wider release graph CI workflow via PR #163
- openssl-backed release proof verification via PR #164
- wider release proof pipeline runner via PR #167
- canonical manifest digest refresh and CI enforcement via PR #169
- manifest publication path via PR #171
- manifest promotion path via PR #175
- manifest promotion policy enforcement via PR #200
- manifest promotion approval enforcement via PR #202
- manifest promotion approval cryptographic verification via PR #207
- release publication gate via PR #211
- registry publication index via PR #212
- filesystem registry adapter via PR #215
- filesystem registry root builder/checker via PR #224
- registry rollback/revocation lifecycle index via PR #237
- local OpenSSL-backed registry metadata signature verification via PR #248
- registry-root metadata and rollback/revocation tranche via PR #324
- tightened registry root and revocation schemas via PR #330

## Current active frontier

Fog Stack is past initial offering definition, local trust-graph construction, first-generation filesystem registry publication, registry-root metadata, rollback/revocation lifecycle indexing, local registry metadata signature verification, and strict registry schema hardening. The active frontier is now Office / Collaboration service hardening, Lattice Studio/Data/GovernAI live-backend readiness, network registry publication, production signing/identity integration, and operator-facing release-distribution UX.

The current release path is:

1. validate bundles and rulepacks
2. emit validation records
3. refresh canonical manifest digests
4. build a manifest publication set
5. promote the publication set through policy
6. require approval and approval-signature verification
7. emit a release publication gate record
8. build a registry publication index
9. publish the gated index and referenced artifacts to a filesystem registry layout
10. emit registry-root metadata and rollback/revocation lifecycle indexes
11. locally verify registry metadata signatures where fixture OpenSSL signing is present
12. validate registry root and revocation metadata against tightened schemas

## Product-pack readiness matrix

| Pack | Readiness | Category | Notes |
|---|---|---|---|
| Fog Stack Access | 70% | product_surface | Most mature customer-facing surface |
| Fog Stack Knowledge | 55% | product_surface | Composition-heavy, operationally mixed |
| Fog Stack Evaluation | 55% | product_surface | More internal than packaged |
| Fog Stack Office / Collaboration | 55% | product_surface | Executable-demo posture; PRs #314–#319 |
| Fog Stack Security / Trust | 35% (standalone) | shared_capability | 80% as platform capability |
| Fog Stack Registry / Release Distribution | 60% | product_surface | Filesystem registry, root metadata, lifecycle index, local signature verification, and strict schemas; PRs #211–#215, #224, #237, #248, #324, #330 |
| Fog Stack Data / GovernAI | 50% | product_surface | Fixture-ready; upgraded from 30%; PRs #299–#308 |
| Fog Stack AI / Lattice Studio | 45% | product_surface | Fixture-ready; upgraded from 20%; PRs #299–#308 |
| Fog Stack Automation | 20% | future_pack | No distinct surface yet |

The detailed taxonomy and per-pack notes live in:
- `docs/FOGSTACK_PACKS.md`
- `catalog/fogstack-packs-v0.1.yaml`

## Current trust/publication graph shape

The release/trust/publication graph now consists of these machine-readable artifacts:

- release manifest
- validation record
- signature verification record
- signature trust record
- cryptographic signature verification record
- release evidence index
- release seal
- release seal signature metadata
- release seal cryptographic verification record
- release proof pipeline outputs
- wider release graph links
- manifest publication set
- promoted manifest publication set
- promotion policy record/check result
- promotion approval record
- promotion approval cryptographic verification record
- release publication gate record
- registry publication index
- filesystem registry publication/check artifacts
- filesystem registry root metadata
- registry-root metadata
- rollback/revocation lifecycle index
- registry metadata signature-verification evidence
- tightened registry root and revocation schemas

## Known gaps and next tranches

The next release-engineering tranche should focus on:

1. **Network registry publication** beyond filesystem registry export.
2. **Production signing and identity binding**: KMS/HSM-backed registry and release signing, external identity-provider binding, and policy-managed key lifecycle.
3. **Client-side rollback/revocation enforcement** so consumers act on lifecycle indexes rather than merely validating their shape.
4. **Signature verification pipeline exit-code hygiene** so digest mismatch and malformed input fail hard at the CLI layer.
5. **Operator-facing release-distribution UX** including one-command local demo, release-readiness dashboards, and pack-specific smoke deployments.
6. **Status and registry docs kept current** whenever publication gates, registry adapters, lifecycle indexes, signing tranches, or schema hardening land.

## Position in the maturity ladder

Fog Stack in `prophet-platform` is now in registry-backed release-distribution hardening. It has moved from offering taxonomy and local trust records into gated, CI-backed, filesystem-registry artifact publication with root metadata, lifecycle index, local signature-verification support, and tightened registry schemas. The immediate risk is stale status documentation or weak CLI semantics causing operators to misread publication readiness.
