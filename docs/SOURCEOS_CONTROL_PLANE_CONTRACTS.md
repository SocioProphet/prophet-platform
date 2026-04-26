# SourceOS control plane contracts v0

This document defines the first platform-native SourceOS control plane contract set for `prophet-platform`.

SourceOS is not treated here as a standalone distro. It is treated as an opt-in agentic operating and fleet lifecycle system that composes:

- an immutable OSTree/Silverblue/CoreOS-style system plane,
- a Nix-managed lifecycle and policy plane,
- separated user and agent spaces,
- risk-proportional isolation for agent work,
- signed release, boot, and proof artifacts,
- local-first operation that can later replicate into local mesh, cloud twin, and cloud mesh topologies.

## Contract goals

The contracts in `contracts/sourceos/` make the SourceOS control plane machine-addressable instead of narrative-only. They are intentionally minimal but strict enough to support a demo and later fleet expansion.

Current contracts:

- `release-set.v0.schema.json` — normal lifecycle release object for system, user, agent, policy, provenance, and assignment metadata.
- `boot-release-set.v0.schema.json` — bootable release object for live, installer, rescue, rollback, and recovery environments.
- `fingerprint.v0.schema.json` — observed runtime/device/workspace report emitted by systems and agent spaces.
- `config-source.v0.schema.json` — Git/Nix source channel object for local-first declarative lifecycle management.

## Planes

### System plane

The system plane is an immutable, rollbackable host substrate. It accepts only policy-approved system base references and boot integration metadata. It must not become the place where desktop preferences, toolchains, browsers, or agent experiments accumulate.

Required outputs:

- booted system base identifier,
- verification status,
- rollback candidates,
- host integration surface version,
- fingerprint emission.

### Lifecycle plane

The lifecycle plane resolves declarative inputs into signed release outputs. For SourceOS v0, Nix and Git are first-class lifecycle primitives, not ad-hoc package managers.

Required outputs:

- resolved bill of materials,
- Nix closure references for user and agent spaces,
- policy bundle references,
- release signatures,
- provenance records.

### User plane

The user plane contains selectable experience profiles: macOS-like GNOME, Windows-like KDE, Linux-native, tiling, accessibility, development, and other user-facing choices. These choices compile into profile references and closures; they do not mutate the system plane directly.

Required outputs:

- selected experience profile,
- closure references,
- host integration requirements,
- compatibility/degraded-parity notes when relevant.

### Agent plane

The agent plane contains tools, runtimes, models, evaluation harnesses, workspace bundles, and isolation choices. Policy may upgrade the selected isolation level when task, data, or tool risk requires it.

Required outputs:

- agent environment closure references,
- isolation profile,
- capability manifest,
- evidence/proof references,
- fingerprint emission.

## Object model

### ReleaseSet

A ReleaseSet is the normal deployment object. It references the system base, user experience closures, agent environment closures, policy bundle, provenance, and assignment scope. It is signed and immutable once promoted.

### BootReleaseSet

A BootReleaseSet is a bootable ReleaseSet derivative. It is used for secure live boot, install, rescue, recovery, rollback, and Apple Silicon boot-picker/recovery-like flows. It can be produced from the same Git/Nix source graph as normal releases.

### Fingerprint

A Fingerprint is observed fact, not desired state. It reports what the device/workspace actually booted or ran: system base, runtime dialect, libc, shell, LSM visibility, isolation mode, active policy, release identifiers, and proof references.

### ConfigSource

A ConfigSource binds a local or remote Git source into the lifecycle plane. It specifies refs, update mode, token reference, flake entrypoint, branch-to-channel mapping, cache policy, and signature requirements.

## Identity and registration

Devices self-register as a primitive. A device generates a keypair locally and presents a device claim. The control plane binds that claim to a user, group, project, or organization only after explicit opt-in enrollment.

Release-1 does not require full cloud mesh. The model is designed so local-host state can later replicate through:

`local host -> local mesh -> cloud twin -> cloud mesh`

without changing the contract objects.

## Security invariants

- Reasoning is not execution.
- Execution is capability-mediated.
- System space is immutable and rollbackable.
- User and agent spaces are separated by design.
- Agent isolation is risk-proportional.
- Tokens are references to secret-door entries, never embedded in Git, Nix stores, logs, or manifests.
- BootReleaseSets and ReleaseSets require integrity metadata and signatures before promotion.
- Fingerprints report observed state and must not be treated as policy declarations.

## Demo objective

The v0 demo objective is lifecycle proof on one Mac M2 device with the SourceOS control plane served through the project site:

1. Device self-registers.
2. A ConfigSource is bound.
3. A ReleaseSet is built from a Git/Nix source.
4. A BootReleaseSet is generated or selected for recovery/install/live path.
5. The device applies the release.
6. The device emits a Fingerprint.
7. The control plane marks the device compliant or noncompliant.
8. Rollback remains available.

## Relationship to nlboot

`SociOS-Linux/nlboot` remains an external evolving boot dependency. SourceOS keeps the nlboot shape where useful: a minimal boot environment announces itself, receives boot instructions, verifies artifacts, and kexecs or installs. The SourceOS upgrade is that the response becomes a signed BootReleaseSet object graph with policy and proof obligations.

## Relationship to Sociosphere

Sociosphere must be aware of SourceOS release, boot, and lifecycle artifacts. This contract set is written so Sociosphere can validate composition, governance, evidence, and workspace registration without owning the boot implementation itself.
