# SourceOS lifecycle state machine v0

This document defines the minimum lifecycle state machine needed to prove SourceOS control-plane behavior on a single Mac M2 demo device while preserving the same object model for later fleet, mesh, and cloud-twin expansion.

## Scope

This state machine governs SourceOS control-plane artifacts only. It does not implement federated learning, cloud mesh replication, or global fleet orchestration in v0. It defines the proof-bearing lifecycle that those systems can later reuse.

## Primary objects

- `ConfigSource`: declarative lifecycle input, usually a Git repository with a Nix flake or lockfile.
- `ReleaseSet`: signed normal lifecycle release for system, user, agent, policy, and provenance state.
- `BootReleaseSet`: signed bootable release for live, installer, rescue, rollback, or recovery flow.
- `Fingerprint`: observed state emitted by a device, workspace, or boot environment.

## States

### 1. ConfigSourceRegistered

A local or remote source is registered with policy boundaries.

Required proof:

- ConfigSource object exists.
- Token reference is a secret-door reference, not a literal token.
- Allowed refs and update mode are declared.

### 2. RefDetected

A source ref is selected or observed.

Allowed triggers:

- manual selection,
- pull update,
- PR branch update,
- tag creation,
- scheduled poll.

Required proof:

- ref name,
- commit/tag identifier where applicable,
- verification result for required signatures/status checks.

### 3. BuildResolved

The lifecycle plane resolves source inputs into build inputs.

Required proof:

- Nix entrypoint resolved,
- lockfile or pin reference captured,
- bill of materials reference created,
- policy compatibility check completed.

### 4. ReleaseBuilt

System, user, and agent outputs are built or selected.

Required proof:

- system base reference,
- user closure references,
- agent environment references,
- policy bundle reference,
- build log/evidence reference.

### 5. ReleaseSigned

A ReleaseSet is signed and becomes immutable for promotion purposes.

Required proof:

- ReleaseSet object,
- signature references,
- signing key identifiers,
- required signature threshold result.

### 6. BootReleaseBuilt

A BootReleaseSet is built or selected when a live, installer, rescue, recovery, or rollback flow is required.

Required proof:

- BootReleaseSet object,
- boot mode list,
- platform entrypoints,
- signed artifact manifest,
- proof reporting requirement.

### 7. Assigned

A ReleaseSet or BootReleaseSet is assigned to a device, user, group, project, organization, or fleet.

Required proof:

- assignment scope kind and identifier,
- policy bundle reference,
- channel and support state,
- rollback candidate where applicable.

### 8. Redeemed

For boot/install/recovery, a one-time boot or enrollment authorization is redeemed.

Required proof:

- device claim,
- authorization mode,
- token TTL,
- redemption result,
- bound ReleaseSet or BootReleaseSet identifier.

### 9. Deployed

The device or workspace applies the release.

Required proof:

- deployment log reference,
- applied release identifier,
- applied system/user/agent refs,
- rollback candidate retained.

### 10. Fingerprinted

The subject emits observed state.

Required proof:

- Fingerprint object,
- observed system and runtime facts,
- active policy reference,
- evidence references.

### 11. ComplianceEvaluated

The control plane evaluates the fingerprint against assigned release and policy.

Possible outcomes:

- `compliant`,
- `noncompliant`,
- `degraded`,
- `unknown`.

Required proof:

- evaluated fingerprint id,
- expected release id,
- policy id,
- decision reason list.

### 12. RollbackAvailable

Rollback remains possible after successful deployment.

Required proof:

- previous system base reference,
- previous user/agent closure references where available,
- rollback BootReleaseSet if used.

### 13. RolledBack

A rollback has been executed.

Required proof:

- rollback trigger,
- target rollback reference,
- post-rollback fingerprint,
- compliance result.

## Transition table

| From | To | Gate |
| --- | --- | --- |
| ConfigSourceRegistered | RefDetected | ref allowed by ConfigSource |
| RefDetected | BuildResolved | signature/status policy satisfied or explicitly waived |
| BuildResolved | ReleaseBuilt | policy compatibility passes |
| ReleaseBuilt | ReleaseSigned | required signature threshold met |
| ReleaseSigned | BootReleaseBuilt | boot/install/recovery requested |
| ReleaseSigned | Assigned | release channel/support transition allowed |
| BootReleaseBuilt | Assigned | boot artifact manifest signed |
| Assigned | Redeemed | single-use/device claim authorization valid, if required |
| Assigned | Deployed | device fetch/apply succeeds |
| Redeemed | Deployed | boot environment verifies artifacts and applies/install/boots |
| Deployed | Fingerprinted | subject emits observed-state record |
| Fingerprinted | ComplianceEvaluated | fingerprint schema valid and policy evaluable |
| ComplianceEvaluated | RollbackAvailable | previous release refs retained |
| ComplianceEvaluated | RolledBack | noncompliant/degraded state triggers rollback policy |
| RollbackAvailable | RolledBack | operator or policy requests rollback |

## Failure handling

Failures must emit evidence. Silent skipping is not permitted.

Required failure facts:

- state where failure occurred,
- object id if available,
- policy gate that failed,
- log/evidence reference,
- recommended next state.

## Demo acceptance criteria

The first M2 demo is considered lifecycle-complete when the control plane can show:

1. ConfigSource registered.
2. ReleaseSet built and signed.
3. BootReleaseSet built or selected for recovery/install/live path.
4. Release assigned to the M2 device.
5. Device self-registers or redeems enrollment.
6. Device applies or stages the release.
7. Device emits Fingerprint.
8. Control plane evaluates compliance.
9. Rollback candidate remains available.

## Sociosphere registration expectation

Every SourceOS ReleaseSet, BootReleaseSet, and Fingerprint should be registerable in Sociosphere as governance-aware platform evidence. Sociosphere does not need to own implementation, but it must see lifecycle object creation, policy gates, and compliance/proof outcomes.
