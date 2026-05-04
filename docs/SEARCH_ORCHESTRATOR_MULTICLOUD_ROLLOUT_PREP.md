# Search Orchestrator Multi-Cloud Rollout Preparation

## Purpose

This document prepares Search Orchestrator for later rollout across hyperscale, sovereign, regional, OpenShift-compatible, OKD-compatible, and bring-your-own-cloud Kubernetes environments.

This is not live rollout evidence. It is the provider-neutral preparation surface. Real production completion still requires actual cluster captures.

## Scope boundary

This is a Search Orchestrator rollout-prep lane, not an Alexandrian Academy validator. Academy is one current consumer path. The provider taxonomy, OpenShift compatibility, storage expectations, and cloud evidence requirements are general deployment concerns for Search Orchestrator.

## Deployment invariant

Every provider rollout must preserve the same Search Orchestrator invariant:

```text
Search Orchestrator deployed from digest-pinned image
→ policy overlay applies provider-safe secret and storage bindings
→ health/config/metrics endpoints prove runtime state without leaking secrets
→ workload evidence is captured for the selected consumer path
→ release evidence records provider, cluster, image, policy, storage, and rollback posture
```

## Major provider taxonomy

### Global hyperscalers

The primary global providers we must model are:

- AWS;
- Microsoft Azure;
- Google Cloud;
- Oracle Cloud Infrastructure;
- IBM Cloud;
- Alibaba Cloud;
- Huawei Cloud;
- Tencent Cloud.

### AI, edge, and developer clouds

The rollout matrix also tracks providers that may matter for AI, edge, developer, bare-metal, and regional deployment:

- Cloudflare;
- Akamai/Linode;
- DigitalOcean;
- Vultr;
- Equinix Metal;
- CoreWeave;
- Crusoe Cloud.

### Regional and sovereign providers

The rollout matrix keeps regional and sovereign candidates because data residency and procurement rules can force provider selection outside the global hyperscaler set.

Examples include OVHcloud, Scaleway, Hetzner, IONOS, STACKIT, Open Telekom Cloud, Sakura Cloud, Naver Cloud, Kakao Cloud, KT Cloud, Core42/G42, STC Cloud, Ooredoo, Liquid Cloud, MTN Cloud, Vodacom Business, Claro/Embratel, Telefonica, Locaweb, UOL Host, Baidu AI Cloud, UCloud, and others.

## OpenShift and OKD compatibility

Search Orchestrator must remain compatible with:

- generic Kubernetes;
- Red Hat OpenShift;
- OKD.

The base deployment should avoid assumptions that break OpenShift restricted security context behavior.

Required compatibility controls:

- run as non-root;
- no privileged container;
- no hostPath dependency;
- `allowPrivilegeEscalation: false`;
- drop all Linux capabilities;
- use `RuntimeDefault` seccomp;
- avoid ConfigMap-backed secret material;
- keep Policy Fabric endpoint Secret-backed;
- use PVC-backed carrier storage;
- keep OpenShift Route as an optional provider overlay rather than a base dependency.

## Evidence required per provider

Each provider rollout must capture:

1. rendered manifests;
2. ArgoCD or GitOps sync evidence;
3. `/healthz` output;
4. `/v1/search/debug/config` output;
5. `/v1/search/debug/metrics` output;
6. selected workload ingest/query proof;
7. carrier or storage artifact proof where enabled;
8. image digest pin verification;
9. Secret or ExternalSecret binding verification;
10. PVC/storage-class binding verification;
11. NetworkPolicy verification or a documented CNI exception;
12. rollback verification.

## Provider-neutral preflight checklist

Before any provider rollout:

1. Verify digest lock exists.
2. Verify rendered image reference is digest-pinned.
3. Verify provider Secret/ExternalSecret path is selected.
4. Verify storage class and PVC binding plan.
5. Verify OpenShift/OKD compatibility constraints.
6. Verify runtime debug endpoints redact paths, URLs, actors, queries, and secrets.
7. Verify rollback and artifact retention policy.

## Completion standard

This preparation lane is complete when the repository contains:

- this document;
- a machine-readable provider matrix;
- a Search Orchestrator multi-cloud rollout evidence template;
- a validator dedicated to this lane;
- a CI workflow for this validator.

Production rollout is complete only after real provider evidence records are captured and committed.
