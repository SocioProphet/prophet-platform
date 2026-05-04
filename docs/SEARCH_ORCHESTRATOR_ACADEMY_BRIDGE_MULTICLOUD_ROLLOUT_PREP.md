# Search Orchestrator Academy Bridge Multi-Cloud Rollout Preparation

## Purpose

This document prepares the Search Orchestrator Academy bridge for later rollout across Google Cloud, Azure, AWS, IBM Cloud, Oracle Cloud, and bring-your-own-cloud/self-hosted Kubernetes environments.

It deliberately does not claim live rollout evidence. Real production completion still requires actual cluster captures. This document defines the provider-neutral preflight surface and the provider-specific evidence placeholders needed when a real cluster becomes available.

## Deployment invariant

Every provider rollout must preserve the same invariant:

```text
Academy LearningSearchRecord
→ Search Orchestrator ingest/query
→ Lampstand carrier artifacts
→ Policy Fabric visibility decision
→ FogStack release/evidence record
```

No provider rollout may add learner action execution, Canon promotion, policy grant creation, or implicit memory writeback.

## Provider matrix

| Provider | Kubernetes substrate | Identity/secrets expectation | Storage expectation | Evidence status |
| --- | --- | --- | --- | --- |
| Google Cloud | GKE or compatible Kubernetes | Workload identity or external secret integration | PVC backed by encrypted persistent disk or CSI-backed storage | template pending |
| Azure | AKS or compatible Kubernetes | Managed/workload identity or external secret integration | PVC backed by encrypted managed disk or CSI-backed storage | template pending |
| AWS | EKS or compatible Kubernetes | IRSA/workload identity or external secret integration | PVC backed by encrypted EBS or CSI-backed storage | template pending |
| IBM Cloud | IKS/ROKS or compatible Kubernetes | Cloud IAM/workload identity or external secret integration | PVC backed by encrypted block/file storage or CSI-backed storage | template pending |
| Oracle Cloud | OKE or compatible Kubernetes | OCI workload identity or external secret integration | PVC backed by encrypted block volume or CSI-backed storage | template pending |
| BYOC/self-hosted | conformant Kubernetes | customer-controlled identity and secret store | encrypted local, Ceph, Longhorn, TopoLVM, or other governed storage | template pending |

## Required evidence per provider

Each provider evidence capture must include:

1. rendered Kustomize manifests for `infra/k8s/search-orchestrator/overlays/policy`;
2. ArgoCD sync evidence for `search-orchestrator-academy-policy`;
3. `/healthz` capture;
4. `/v1/search/debug/config` capture;
5. `/v1/search/debug/metrics` capture;
6. Academy ingest and query proof;
7. Lampstand carrier artifact proof;
8. rollback verification;
9. image digest pin verification;
10. secret/ExternalSecret binding verification;
11. PVC/storage-class verification;
12. NetworkPolicy verification or an explicit provider reason if the cluster CNI does not enforce NetworkPolicy.

## Provider-neutral preflight checklist

Before deploying to any provider:

1. Verify the image lock exists at `releases/images/search-orchestrator.image-lock.json`.
2. Verify the policy overlay includes `image-patch.yaml`.
3. Verify the rendered manifests use an image digest, not a floating tag.
4. Verify Policy Fabric endpoint is Secret-backed, not ConfigMap-backed.
5. Verify `/v1/search/debug/config` redaction behavior in local or staged runtime.
6. Verify `/v1/search/debug/metrics` returns counters only.
7. Verify PVC, ServiceAccount, Role, RoleBinding, and NetworkPolicy are present.
8. Verify rollback commands and artifact-retention rules are documented before rollout.

## Cloud-specific notes

### Google Cloud

Expected later evidence:

- GKE cluster reference;
- workload identity or secret bridge record;
- storage class and PVC binding evidence;
- ArgoCD sync output;
- endpoint captures.

### Azure

Expected later evidence:

- AKS cluster reference;
- managed/workload identity or secret bridge record;
- storage class and PVC binding evidence;
- ArgoCD sync output;
- endpoint captures.

### AWS

Expected later evidence:

- EKS cluster reference;
- IAM/workload identity or secret bridge record;
- storage class and PVC binding evidence;
- ArgoCD sync output;
- endpoint captures.

### IBM Cloud

Expected later evidence:

- IKS or OpenShift cluster reference;
- Cloud IAM or secret bridge record;
- storage class and PVC binding evidence;
- ArgoCD sync output;
- endpoint captures.

### Oracle Cloud

Expected later evidence:

- OKE cluster reference;
- OCI identity or secret bridge record;
- storage class and PVC binding evidence;
- ArgoCD sync output;
- endpoint captures.

### BYOC/self-hosted

Expected later evidence:

- cluster identity and owner record;
- secret-store profile;
- storage backend profile;
- ArgoCD or GitOps controller evidence;
- endpoint captures.

## Completion standard

The multi-cloud rollout preparation is complete when the repository contains:

- this preparation guide;
- a machine-readable provider matrix;
- a rollout evidence template;
- validation that all expected provider entries and evidence fields are present.

The production rollout itself is complete only after real provider evidence records are captured and committed.
