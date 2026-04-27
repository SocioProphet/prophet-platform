# Prophet Platform Container Build Substrate

Status: draft
Owner: Prophet Platform
Consumes:
- SocioProphet/socioprophet-standards-storage: `standards/evidence-bundle-standard.v1.md`
- SocioProphet/socioprophet-standards-storage: `standards/evaluation-record-standard.v1.md`
- SocioProphet/socioprophet-standards-knowledge: `standards/evaluation-fabric-standard.v1.md`
- SocioProphet/socioprophet-standards-knowledge: `standards/ray-learning-ecosystem-standard.v1.md`
- SocioProphet/sociosphere: `standards/angel-of-the-lord/README.md`
- `docs/SOURCEOS_CONTROL_PLANE_CONTRACTS.md`

## Current observed substrate

This repository already contains at least one container image build workflow:

- `.github/workflows/search-orchestrator-image.yml`
- `services/search-orchestrator/Dockerfile`
- GHCR image naming under `ghcr.io/socioprophet/prophet-platform/search-orchestrator`
- digest evidence emitted as an uploaded artifact
- pinned image reference emitted as `image@digest`

That is the correct image evidence pattern but it must become repo-wide and component-addressable.

## Host/system substrate rule

Prophet Platform container images are designed to deploy onto the SourceOS system plane, not to define the host operating system.

The canonical host/system substrate is:

```text
FCOS / Fedora CoreOS, Silverblue, or compatible OSTree immutable Fedora-family substrate
```

This aligns with the SourceOS control-plane contract, which defines SourceOS as an immutable OSTree/Silverblue/CoreOS-style system plane with Nix-managed lifecycle and policy above it.

Ubuntu, Debian, or other mutable general-purpose distributions must not be introduced as the assumed host substrate for Prophet Platform deployment. They may appear only as:

- upstream development compatibility references;
- temporary local developer environments;
- explicitly documented non-canonical compatibility lanes;
- container builder stages when justified and not leaked into runtime or host assumptions.

## Container runtime image rule

Service container images should be minimal, reproducible OCI artifacts with digest evidence. Runtime images should prefer minimal, hardened, non-Ubuntu bases when practical, such as:

- `scratch` or distroless/static images for static Go binaries;
- Wolfi/Chainguard-style minimal images where supply-chain policy permits;
- UBI/RHEL/Fedora-family minimal images where Fedora-family compatibility is required;
- Nix-built or apko-built images where deterministic closure evidence is required.

If a Debian/Ubuntu-derived runtime image is used, the component inventory must include a justification and migration target. Such an image is not the SourceOS host substrate.

## Purpose

Every Prophet Platform runnable component must declare how it is built, packaged, pinned, scanned, evaluated, and promoted. Container images are not incidental build outputs; they are release evidence objects.

This contract covers:

- Go services such as `apps/api` and `apps/gateway`;
- Python tooling and workers where they become services;
- Ray/KubeRay services where model learning or serving is involved;
- Beam pipeline containers where durable data processing is involved;
- Fog Stack packs and SourceOS control-plane components when packaged here;
- any future service under `services/` or `apps/`.

## Canonical build doctrine

```text
component source -> deterministic container build -> image digest -> SBOM/provenance -> evaluation record -> Angel review where required -> FCOS/Silverblue deployment target -> promotion or remediation
```

## Required object: ContainerComponent

Each runnable component must have an entry in a component inventory.

```yaml
id: stable component identifier
name: human readable name
source_path: repository path
component_type: go_service | python_service | worker | ray_service | beam_pipeline | cli | gateway | api | ui | other
build_context: repository-relative path
containerfile: Dockerfile | Containerfile | apko | ko | nix2container | other
runtime_base: scratch | distroless | wolfi | ubi_minimal | fedora_minimal | nix | other
runtime_base_justification: required when runtime_base is other, debian, or ubuntu
host_substrate: fcos | silverblue | ostree_fedora_family | sourceos_system_plane
image_registry: ghcr.io/socioprophet/prophet-platform
image_name: image name without tag
tags: main, sha, semver, channel, or release tags
digest_required: true
sbom_required: true
provenance_required: true
vulnerability_scan_required: true
evaluation_record_required: true
angel_required: true | false | conditional
promotion_gate: CI, Sociosphere, Delivery Excellence, standards review, or manual review
runtime_class: platform | mlops | ray | beam | sourceos | fogstack | other
```

## Required object: ContainerBuildEvidence

```yaml
id: stable identifier
component_id: ContainerComponent id
source_sha: git commit SHA
workflow_ref: CI workflow, local build, or release process
build_tool: docker_buildx | ko | apko | nix | buildpacks | bazel | other
image_ref: tag reference
image_digest: immutable digest
pinned_ref: image@digest
runtime_base: runtime base family
host_substrate_target: FCOS/Silverblue/OSTree Fedora-family target
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

The inventory must include all runnable components and their expected build substrate.

## Minimum image build requirements

Every production or demo image must:

1. build from a declared context and Containerfile/Dockerfile/build mechanism;
2. publish or produce an immutable digest;
3. emit a pinned `image@digest` reference;
4. identify its runtime base and canonical FCOS/Silverblue/OSTree deployment target;
5. produce build evidence;
6. produce an SBOM where supported;
7. produce provenance where supported;
8. run component-level tests or smoke checks;
9. run vulnerability/supply-chain checks where supported;
10. be promotable or rejectable through an evaluation record;
11. pass Angel of the Lord review when release, public exposure, runtime policy, or source-exposure risk requires it.

## Runtime-specific requirements

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

A container image must not be promoted when:

- image digest is missing;
- build evidence is missing;
- component is absent from inventory;
- host substrate is not FCOS/Silverblue/OSTree Fedora-family or SourceOS system plane;
- runtime base is Debian/Ubuntu-derived without explicit justification and migration target;
- SBOM/provenance is required but missing;
- vulnerability findings are blocker/high and unresolved;
- evaluation record is missing;
- regression check is missing for epoch-bearing components;
- Angel review blocks release or requires restricted handling;
- runtime is misclassified, especially Clipper as an active primary runtime.

## First inventory targets

Initial repo-visible targets include:

```yaml
- id: search_orchestrator
  source_path: services/search-orchestrator
  existing_workflow: .github/workflows/search-orchestrator-image.yml
  current_status: existing_buildx_ghcr_digest_evidence
- id: socioprophet_api
  source_path: apps/api/cmd/socioprophet-api
  current_status: needs_declared_container_build
- id: tritrpc_gateway
  source_path: apps/gateway/cmd/tritrpc-gateway
  current_status: needs_declared_container_build
```

Additional services, workers, Ray components, Beam components, and Fog Stack packs must be added as they become runnable components.
