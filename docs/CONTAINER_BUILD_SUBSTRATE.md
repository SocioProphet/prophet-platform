# Prophet Platform Container Build Substrate

Status: draft
Owner: Prophet Platform
Consumes:
- SocioProphet/socioprophet-standards-storage: `standards/evidence-bundle-standard.v1.md`
- SocioProphet/socioprophet-standards-storage: `standards/evaluation-record-standard.v1.md`
- SocioProphet/socioprophet-standards-knowledge: `standards/evaluation-fabric-standard.v1.md`
- SocioProphet/socioprophet-standards-knowledge: `standards/ray-learning-ecosystem-standard.v1.md`
- SocioProphet/socioprophet-standards-knowledge: `standards/immutable-image-substrate-standard.v1.md`
- SocioProphet/sociosphere: `standards/angel-of-the-lord/README.md`
- SocioProphet/sociosphere: `governance/SOURCEOS_SUBSTRATE_BOUNDARIES.yaml`
- SociOS-Linux/SourceOS: `docs/ARTIFACT_TRUTH.md`
- SociOS-Linux/socios: `docs/FCOS_FOREMAN_KATELLO_SUBSTRATE.md`
- SociOS-Linux/socios: `foreman/KATELLO_CONTENT_MODEL.md`
- SourceOS-Linux/sourceos-spec: shared content/build/release contracts
- `docs/SOURCEOS_CONTROL_PLANE_CONTRACTS.md`
- `docs/SOURCEOS_M2_LIFECYCLE_PROOF.md`

## Authority split

Prophet Platform does not own the full SourceOS image-production substrate. It consumes and integrates the existing SourceOS/SociOS authority split:

| Concern | Canonical owner | Prophet Platform role |
|---|---|---|
| Artifact truth: flavors, coreos-assembler inputs, Butane/Ignition, installer profiles, channels, manifests | `SociOS-Linux/SourceOS` | reference and consume artifact truth |
| Foreman/Katello, Smart Proxy, Tekton build/customize/sign/publish/promote, Argo CD, enrollment/rollout/promotion automation | `SociOS-Linux/socios` | invoke or integrate production automation lanes |
| Shared typed contracts and content/build/release object families | `SourceOS-Linux/sourceos-spec` | conform to shared schemas and URN discipline |
| Governance boundary map | `SocioProphet/sociosphere` | register and enforce source-of-truth boundaries |
| Product/control-plane proof and M2 lifecycle demo | `SocioProphet/prophet-platform` | model ReleaseSet/BootReleaseSet, website/control-plane integration, M2 proof bundle |
| Governed execution of bundles | `SocioProphet/agentplane` | validate/place/run/evidence/replay image-production bundle executions |

Do not duplicate Foreman/Katello semantics in Prophet Platform. The production lane already exists in `SociOS-Linux/socios`.

## Current observed substrate

This repository already contains at least one container image build workflow:

- `.github/workflows/search-orchestrator-image.yml`
- `services/search-orchestrator/Dockerfile`
- GHCR image naming under `ghcr.io/socioprophet/prophet-platform/search-orchestrator`
- digest evidence emitted as an uploaded artifact
- pinned image reference emitted as `image@digest`

That is the correct image evidence pattern but it must become repo-wide and component-addressable.

The SourceOS production-image path is not invented here. The existing path is:

```text
SociOS-Linux/SourceOS artifact truth
→ SociOS-Linux/socios Tekton live ISO customization / publish lanes
→ Foreman/Katello Product / Repository / Content View / Lifecycle Environment / Activation Key model
→ SourceOS ReleaseSet / BootReleaseSet / EvidenceBundle / ProofIndex consumption in Prophet Platform
→ Agentplane evidence wrapper where execution is delegated through bundles
```

## Host/system substrate rule

Prophet Platform container images are designed to deploy onto the SourceOS system plane, not to define the host operating system.

The canonical host/system substrate is:

```text
FCOS / Fedora CoreOS, Silverblue, Kinoite, or compatible OSTree immutable Fedora-family substrate
```

This aligns with the SourceOS control-plane contract, which defines SourceOS as an immutable OSTree/Silverblue/CoreOS-style system plane with Nix-managed lifecycle and policy above it.

Ubuntu, Debian, Alpine, or other mutable general-purpose distributions must not be introduced as the assumed host substrate for Prophet Platform deployment. They may appear only as:

- upstream development compatibility references;
- temporary local developer environments;
- explicitly documented non-canonical compatibility lanes;
- container builder stages when justified and not leaked into runtime or host assumptions.

## Immutable image family selection

The platform must distinguish immutable host images, recovery images, service images, Beam/Ray workload images, and Nix user/agent closures. These are not interchangeable.

| Need | Preferred substrate | Bloat control |
|---|---|---|
| Headless/server host | FCOS/CoreOS-like OSTree image | No desktop, no app suites, no toolchains |
| Desktop/workstation host | Silverblue/Kinoite/OSTree desktop host | Only host integration primitives; DE/app choice lives in Nix user closures |
| Recovery/install/rollback | Minimal SourceOS recovery image | Only network, enrollment, fetch, verify, apply, rollback |
| API/gateway/service | scratch/distroless/Wolfi/UBI-minimal OCI | No package manager, shell, compiler, or mutable runtime unless justified |
| Durable data pipeline | Beam pipeline image | Beam lineage and replayability evidence required |
| Ray learning/serving | Ray/KubeRay workload image | Consumes Beam-produced datasets; Ray Data is local adapter |
| User apps and DEs | Nix user closure | Choice without system-plane bloat |
| Agent tools/runtimes | Nix agent closure or isolated OCI/microVM | Policy-governed capability and rollback |

## Desktop/server bloat rule

Desktop and server substrates must remain role-specific:

- Server images use FCOS/CoreOS-like immutable hosts and should not include desktop stack packages.
- Desktop host images use Silverblue/Kinoite-style immutable hosts and should include only graphics/audio/portal/session primitives needed to host user-plane closures.
- GNOME, KDE, macOS-like, Windows-like, developer toolchains, browsers, office apps, model tools, and agent runtimes must compile into Nix-managed user or agent closures unless a host-integration exception is approved.
- Exceptions require an evidence record, owner, expiration or migration target, and Angel review when release or source-exposure risk applies.

## Container runtime image rule

Service container images should be minimal, reproducible OCI artifacts with digest evidence. Runtime images should prefer minimal, hardened, non-Ubuntu bases when practical, such as:

- `scratch` or distroless/static images for static Go binaries;
- Wolfi/Chainguard-style minimal images where supply-chain policy permits;
- UBI/RHEL/Fedora-family minimal images where Fedora-family compatibility is required;
- Nix-built or apko-built images where deterministic closure evidence is required.

If a Debian/Ubuntu/Alpine-derived runtime image is used, the component inventory must include a justification and migration target. Such an image is not the SourceOS host substrate.

## Purpose

Every Prophet Platform runnable component must declare how it is built, packaged, pinned, scanned, evaluated, and promoted. Container images are not incidental build outputs; they are release evidence objects.

This contract covers:

- Go services such as `apps/api` and `apps/gateway`;
- Python tooling and workers where they become services;
- Ray/KubeRay services where model learning or serving is involved;
- Beam pipeline containers where durable data processing is involved;
- Fog Stack packs and SourceOS control-plane components when packaged here;
- SourceOS image-production control-plane integrations that consume `SourceOS`/`socios`/`sourceos-spec` authorities;
- any future service under `services/` or `apps`.

## Canonical build doctrine

```text
component source -> deterministic container/image build -> image digest or OSTree ref -> SBOM/provenance -> evaluation record -> Angel review where required -> Foreman/Katello lifecycle where applicable -> FCOS/Silverblue deployment target -> promotion or remediation
```

## Required object: ContainerComponent

Each runnable component must have an entry in a component inventory.

```yaml
id: stable component identifier
name: human readable name
source_path: repository path
component_type: go_service | python_service | worker | ray_service | beam_pipeline | sourceos_image_lane | cli | gateway | api | ui | other
image_family: fcos_server | silverblue_desktop | sourceos_recovery | minimal_service_oci | beam_pipeline | ray_learning | nix_user_agent_closure | other
build_context: repository-relative path or external authority reference
containerfile: Dockerfile | Containerfile | apko | ko | nix2container | sourceos_socios_tekton | other
runtime_base: scratch | distroless | wolfi | ubi_minimal | fedora_minimal | nix | ostree | fcos_live_iso | other
runtime_base_justification: required when runtime_base is other, debian, ubuntu, or alpine
host_substrate: fcos | silverblue | kinoite | ostree_fedora_family | sourceos_system_plane
sourceos_artifact_truth_ref: optional `SociOS-Linux/SourceOS` path
socios_automation_ref: optional `SociOS-Linux/socios` path
sourceos_spec_ref: optional `SourceOS-Linux/sourceos-spec` schema or family
katello_product: optional Product name
katello_repository: optional Repository name
katello_content_view: optional Content View reference
katello_lifecycle_environment: optional dev | qa | prod | site ring
image_registry: registry or not_applicable
image_name: image name or not_applicable
tags: main, sha, semver, channel, or release tags
digest_required: true
sbom_required: true
provenance_required: true
vulnerability_scan_required: true
evaluation_record_required: true
angel_required: true | false | conditional
promotion_gate: CI, Sociosphere, Delivery Excellence, standards review, Katello lifecycle promotion, or manual review
runtime_class: platform | mlops | ray | beam | sourceos | fogstack | other
```

## Required object: ContainerBuildEvidence

```yaml
id: stable identifier
component_id: ContainerComponent id
source_sha: git commit SHA
workflow_ref: CI workflow, local build, socios Tekton pipeline, or release process
build_tool: docker_buildx | ko | apko | nix | buildpacks | bazel | ostree_compose | coreos_installer | socios_tekton | other
image_family: immutable image family
image_ref: tag reference
image_digest: immutable digest
ostree_ref: optional OSTree ref
katello_content_ref: optional Katello content reference
pinned_ref: image@digest or content-addressed artifact reference
runtime_base: runtime base family
host_substrate_target: FCOS/Silverblue/Kinoite/OSTree Fedora-family target
sbom_ref: SBOM artifact reference
provenance_ref: SLSA/in-toto/build provenance reference when available
vulnerability_scan_ref: scan artifact reference
evaluation_record_ref: EvaluationRecord reference
angel_epoch_grade_ref: AngelEpochGrade reference where required
created_at: ISO-8601 datetime
```

## Required inventory path

The platform should maintain:

```text
releases/images/component-inventory.v1.yaml
```

The inventory must include all runnable components and their expected build substrate. SourceOS image-production lanes must reference their canonical `SourceOS` artifact-truth path and `socios` automation path.

## Minimum image build requirements

Every production or demo image must:

1. build from a declared context and Containerfile/Dockerfile/build mechanism, or from the declared `SourceOS` artifact-truth + `socios` automation lane;
2. publish or produce an immutable digest, OSTree ref, closure hash, or Katello content reference;
3. emit a pinned `image@digest` or content-addressed artifact reference;
4. identify its image family, runtime base, and canonical FCOS/Silverblue/Kinoite/OSTree deployment target;
5. produce build evidence;
6. produce an SBOM where supported;
7. produce provenance where supported;
8. run component-level tests or smoke checks;
9. run vulnerability/supply-chain checks where supported;
10. be promotable or rejectable through an evaluation record;
11. pass Angel of the Lord review when release, public exposure, runtime policy, or source-exposure risk requires it.

## Runtime-specific requirements

### SourceOS image-production lanes

SourceOS image-production lanes must reference:

- `SociOS-Linux/SourceOS` artifact truth: flavor, cosa, Butane/Ignition, installer profile, channel, manifest;
- `SociOS-Linux/socios` automation: Foreman/Katello substrate, Tekton customize/sign/publish/promote lanes, smoke runner;
- `SourceOS-Linux/sourceos-spec` shared content/build/release object family where applicable;
- ReleaseSet or BootReleaseSet proof refs in Prophet Platform;
- EvidenceBundle / EvaluationRecord / ProofIndex refs.

Foreman/Katello own provisioning/content/lifecycle. They are not the image composer. CoreOS/FCOS tooling, coreos-installer, cosa/build-source material, Nix closures, and SourceOS artifact truth define what is built.

### Beam pipeline containers

Beam pipeline containers must reference:

- Beam pipeline source;
- data lineage and replayability evidence;
- DataPipelineDecision record;
- input/output dataset references;
- EvaluationRecord.

Beam is the canonical durable data-processing substrate.

### Ray / KubeRay containers

Ray-related containers must reference:

- RayLearningRun;
- Ray component: Ray Train, Tune, RLlib, Serve, or KubeRay;
- runtime environment reference;
- model/checkpoint references where applicable;
- evaluation and regression records.

Ray Data is a Ray-local adapter unless a Beam exception is documented.

### Model serving containers

Serving containers must classify runtime as:

```yaml
serving_runtime: ray_serve | kuberay | kserve | seldon | triton | bentoml | mlflow | torchserve | tensorflow_serving | legacy_clipper | other
runtime_status: primary | supported | specialized | experimental | legacy_reference | deprecated
```

Ray Serve and KubeRay are the primary path. Clipper is legacy-reference only.

## Blocking conditions

A container or immutable image must not be promoted when:

- image digest, OSTree ref, Katello content reference, or closure hash is missing;
- build evidence is missing;
- component is absent from inventory;
- SourceOS image-production lane lacks `SourceOS` artifact-truth reference;
- SourceOS image-production lane lacks `socios` automation reference;
- image family is missing or wrong for the intended role;
- host substrate is not FCOS/Silverblue/Kinoite/OSTree Fedora-family or SourceOS system plane;
- server images include desktop payload without an approved exception;
- desktop host images include app/toolchain/agent bloat outside host integration primitives;
- runtime base is Debian/Ubuntu/Alpine-derived without explicit justification and migration target;
- SBOM/provenance is required but missing;
- vulnerability findings are blocker/high and unresolved;
- evaluation record is missing;
- regression check is missing for epoch-bearing components;
- Angel review blocks release or requires restricted handling;
- runtime is misclassified, especially Clipper as an active primary runtime.

## First inventory targets

Initial repo-visible targets include:

```yaml
- id: sourceos_m2_lifecycle_proof
  source_path: tools/build_sourceos_m2_lifecycle_proof.py
  current_status: deterministic_local_proof_existing
- id: sourceos_m2_recovery_boot_release_set
  source_path: docs/SOURCEOS_M2_LIFECYCLE_PROOF.md + tools/build_sourceos_m2_lifecycle_proof.py
  current_status: proof_artifact_only_not_live_boot
- id: sourceos_fcos_live_iso_production_lane
  sourceos_artifact_truth_ref: SociOS-Linux/SourceOS installer/flavors/channels/manifests
  socios_automation_ref: SociOS-Linux/socios pipelines/tekton/pipeline-customize-live-iso.yaml
  current_status: existing_socios_scaffold_to_integrate
- id: search_orchestrator
  source_path: services/search-orchestrator
  existing_workflow: .github/workflows/search-orchestrator-image.yml
  current_status: existing_buildx_ghcr_digest_evidence
- id: socioprophet_api
  source_path: apps/api/cmd/socioprophet-api
  current_status: deployable_buildx_ghcr_digest_evidence
- id: tritrpc_gateway
  source_path: apps/gateway/cmd/tritrpc-gateway
  current_status: deployable_buildx_ghcr_digest_evidence
```

Additional desktop host images, server host images, recovery images, services, workers, Ray components, Beam components, and Fog Stack packs must be added as they become runnable components.
