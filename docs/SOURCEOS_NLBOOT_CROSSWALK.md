# SourceOS nlboot crosswalk

This note records the current alignment between the `prophet-platform` SourceOS M2 lifecycle proof fixture and the merged `SociOS-Linux/nlboot` M2 recovery fixture.

## Purpose

The SourceOS control-plane contracts model the lifecycle object graph:

- `ConfigSource`
- `ReleaseSet`
- `BootReleaseSet`
- `Fingerprint`
- `ComplianceResult`
- `ProofIndex`

`nlboot` models the safe boot/recovery planner input path:

- `SignedBootManifest`
- `EnrollmentToken`
- trusted release key material
- side-effect-free `BootPlan`

This crosswalk prevents those two fixture sets from drifting while we build toward the M2 lifecycle proof.

## Current mapping

| SourceOS proof artifact | nlboot fixture field |
|---|---|
| `release-set.json.system.base_ref` | `base_release_set_ref` |
| `boot-release-set.json.artifacts[].uri` for manifest | `manifest_id` |
| `boot-release-set.json.artifacts[].uri` for kernel/initrd/rootfs | `artifacts.kernel_ref`, `artifacts.initrd_ref`, `artifacts.rootfs_ref` |
| `nlboot-crosswalk.json.nlboot_token_id` | `EnrollmentToken.token_id` |
| `nlboot-crosswalk.json.nlboot_signer_ref` | `SignedBootManifest.signer_ref` |

## Safety boundary

The crosswalk is a proof fixture, not an execution path.

It does not add:

- artifact fetching
- host mutation
- disk writes
- `kexec`
- remote state mutation

The nlboot side remains safe-planning only and produced plans remain `execute=false`.

## CI coverage

`tools/smoke_sourceos_m2_lifecycle_proof.py` now verifies that:

1. the lifecycle proof bundle includes `nlboot-crosswalk.json`,
2. the crosswalk references the generated SourceOS `ReleaseSet`,
3. the crosswalk references the generated SourceOS `BootReleaseSet`, and
4. the generated `BootReleaseSet` includes the nlboot manifest id as an artifact URI.

## Follow-on

Next useful tranche:

1. publish the generated M2 proof bundle through the filesystem registry path,
2. make nlboot consume a registry-published manifest fixture without side effects,
3. emit a synthetic boot `Fingerprint`, and
4. validate that fingerprint against the assigned `ReleaseSet`.
