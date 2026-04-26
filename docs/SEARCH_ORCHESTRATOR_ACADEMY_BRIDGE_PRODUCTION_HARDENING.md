# Search Orchestrator Academy Bridge Production Hardening

## Purpose

This guide records the production hardening requirements for the Search Orchestrator Academy bridge.

The bridge is responsible for receiving Alexandrian Academy `LearningSearchRecord` artifacts, enforcing visibility through local fallback or Policy Fabric decisions, and optionally emitting Lampstand carrier artifacts. Production hardening must preserve those boundaries without adding learner action execution, Canon promotion, policy grant creation, or implicit memory writeback.

## Hardening controls

### Workload identity and RBAC

The deployment uses a dedicated Kubernetes `ServiceAccount` named `search-orchestrator`.

The default `Role` grants only read access to ConfigMaps:

- `get`
- `list`
- `watch`

No Secret read permission is granted through RBAC. Secret values are mounted into the workload only through explicit Kubernetes Secret or ExternalSecret binding.

### Pod and container security

Required security controls:

- `runAsNonRoot: true`
- non-zero UID/GID
- `seccompProfile.type: RuntimeDefault`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`
- Linux capabilities dropped with `drop: ["ALL"]`
- writable `/tmp` provided through `emptyDir`
- runtime path mounted separately at `/run/prophet-platform`

### Persistent storage

Production carrier mode must not rely on `emptyDir` for data-bearing paths.

The base deployment uses a `PersistentVolumeClaim` named `search-orchestrator-data` mounted at:

- `/var/lib/prophet-platform`

Recommended production policy:

- use a storage class with encryption at rest;
- prefer `ReadWriteOnce` unless the deployment becomes horizontally scaled with repository-level concurrency controls;
- treat Lampstand carrier artifacts as evidence-bearing outputs;
- do not delete carrier artifacts during rollback unless corruption is confirmed and backup exists.

### Network policy

The base network policy restricts:

- ingress to port `8080` from the `prophet-platform` namespace;
- egress to Kubernetes DNS;
- egress to `prophet-platform` namespace port `8080` for internal Policy Fabric-style calls.

Cluster-specific overlays may refine selectors further once namespace labels and service labels are stable.

### Policy Fabric endpoint secret handling

The policy overlay must not store `SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT` in a ConfigMap.

Production options:

1. Kubernetes Secret example:
   - `infra/k8s/search-orchestrator/overlays/policy/policy-fabric-secret.example.yaml`
2. ExternalSecret example:
   - `infra/k8s/search-orchestrator/overlays/policy/policy-fabric.externalsecret.example.yaml`

The deployment reads the endpoint through a Secret-backed environment variable.

The debug endpoint may report that a Policy Fabric endpoint is configured, but it must never return the URL.

### Image pinning

The base deployment still uses a development image tag as a placeholder.

Production release must replace that image with a digest-pinned reference before production rollout. Example target shape:

```text
ghcr.io/socioprophet/prophet-platform/search-orchestrator@sha256:<digest>
```

Do not use floating tags for production rollout.

## Required validation evidence

The following files must remain validated by `tools/validate_search_orchestrator_academy_deploy.py`:

- base deployment;
- service account and RBAC;
- PVC;
- network policy;
- policy Secret and ExternalSecret examples;
- carrier and policy overlays;
- rollout checklist;
- release readout;
- observability runbook.

## Production readiness status

This hardening closes the first production-readiness gap for Kubernetes posture. Remaining production closure still requires:

- image build and digest-pinning automation;
- cluster-specific storage-class selection;
- cluster-specific SecretStore binding;
- alerting and dashboard deployment;
- production rollout evidence from a real cluster.
