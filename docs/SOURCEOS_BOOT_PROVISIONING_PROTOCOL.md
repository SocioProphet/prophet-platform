# SourceOS boot provisioning protocol v0

This protocol defines how SourceOS serves secure live, installer, rescue, rollback, and recovery environments from the control plane.

It is intentionally compatible with two implementation families:

- Apple Silicon boot-picker / Asahi-style installer entry flows.
- Generic PC/Purism/UEFI flows using iPXE, HTTPBoot, ISO, disk-image, or nlboot-style bootstrap media.

## Design position

Classic PXE semantics are not assumed globally. SourceOS defines PXE-like semantics:

1. a minimal boot substrate starts first,
2. it proves or claims device identity,
3. it fetches signed boot instructions,
4. it verifies boot artifacts,
5. it boots, installs, repairs, or rolls back,
6. it reports proof artifacts.

On Apple Silicon, this maps to boot-picker-visible normal and recovery/installer entries. On PC-class systems, this can map to iPXE/UEFI HTTPBoot or a small persistent nlboot-like medium.

## Actors

### Boot environment

A minimal environment that can:

- collect device claim data,
- acquire restricted network access,
- redeem an authorization token when required,
- fetch a BootReleaseSet,
- verify signatures and artifact digests,
- boot/kexec/install/repair/rollback according to policy,
- emit a Fingerprint and boot log reference.

### Control plane

The web/API management surface that:

- registers devices,
- creates or assigns ReleaseSets and BootReleaseSets,
- issues single-use enrollment or boot codes,
- binds codes to device claims,
- serves signed manifests and artifacts,
- records proofs and compliance status.

### Sociosphere

The workspace controller and governance plane that should observe SourceOS lifecycle artifacts and evidence. Sociosphere is not the boot server in v0, but it must be able to register and validate SourceOS composition/evidence objects.

## Boot-time authorization flow

1. Boot environment starts.
2. Boot environment generates or reads a device claim.
3. User enters a one-time code, or the environment presents mTLS/device credentials.
4. Control plane verifies:
   - code validity,
   - TTL,
   - one-time-use status,
   - device claim binding,
   - assigned ReleaseSet/BootReleaseSet,
   - policy compatibility.
5. Control plane returns a signed BootReleaseSet manifest or a pointer to one.
6. Boot environment downloads artifacts.
7. Boot environment verifies all artifact digests and manifest signatures.
8. Boot environment executes the authorized mode: live, installer, rescue, rollback, or recovery.
9. Boot environment emits proof artifacts.
10. Control plane evaluates compliance.

## Authorization modes

### none

Allowed only for public demo artifacts that do not write disks, do not enroll devices, and do not expose secrets.

### single_use_code

Preferred Release-1 enrollment mode. The code must be:

- time-bound,
- one-time-use,
- bound to a device claim at redemption,
- bound to an authorized BootReleaseSet or ReleaseSet.

### device_claim

Used after a device is enrolled. The boot environment presents a device identity key or claim and receives only assignments authorized for that device.

### mtls

Optional stronger channel for later fleet operation.

### signed_offline_blob

Used when online redemption is unavailable. The blob must still encode expiration, assignment, and signature metadata.

## Capability modes

A BootReleaseSet must declare what the boot environment is allowed to do.

### live

- Disk write: denied by default.
- Network: restricted by default.
- kexec: optional.
- Enrollment: optional.

### installer

- Disk write: scoped.
- Network: restricted.
- kexec/install: allowed.
- Enrollment: allowed when policy permits.

### recovery

- Disk write: scoped.
- Rollback: allowed.
- Repair user/agent closures: allowed.
- Re-enrollment/key rotation: allowed when policy permits.

### rollback

- Disk write: scoped to rollback target.
- Network: optional.
- Required output: post-rollback Fingerprint.

## Apple Silicon mapping

Apple Silicon does not provide generic firmware PXE semantics. SourceOS should expose normal and recovery/installer entries as boot-picker-visible operating system or installer entries via the Apple Silicon/Asahi-compatible path.

The SourceOS recovery entry should behave like a recovery environment within Linux-managed constraints:

- fetch assigned BootReleaseSets,
- repair/re-pin Nix closures,
- rebase or roll back the system base,
- rotate device keys or re-enroll,
- emit proof artifacts.

The contract target is capability parity with recovery-style workflows, not literal execution inside Apple 1TR recoveryOS.

## nlboot mapping

The nlboot shape is retained as a useful implementation primitive:

- minimal boot environment,
- announce endpoint,
- server-directed boot instructions,
- optional claim code/client certificate,
- kexec into target system,
- offline fallback.

SourceOS changes the payload semantics:

- boot instructions become a signed BootReleaseSet manifest,
- hashes are SHA-256 minimum,
- disk-write/kexec/rollback are policy-gated,
- proof reporting is mandatory for managed flows,
- last-known-good fallback is represented as a signed offline fallback reference.

## Required proof artifacts

Every managed boot operation must emit:

- boot environment Fingerprint,
- manifest digest list,
- applied ReleaseSet or BootReleaseSet id,
- boot/provisioning log reference,
- compliance result or failure evidence.

## Non-goals for v0

- No global cloud mesh implementation.
- No federated learning lifecycle.
- No guarantee of hardware remote attestation.
- No claim that SourceOS can run arbitrary code inside Apple-signed recoveryOS.

## Acceptance criteria

A v0 boot proof passes when a test device can:

1. boot into a minimal SourceOS recovery/provisioning environment,
2. redeem or present authorization,
3. fetch a signed BootReleaseSet,
4. verify artifact digests,
5. perform live/install/recovery/rollback behavior according to policy,
6. emit a valid Fingerprint,
7. appear as compliant or noncompliant in the control plane.
