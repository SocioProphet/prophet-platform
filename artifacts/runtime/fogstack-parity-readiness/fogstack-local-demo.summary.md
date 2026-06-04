# FogStack Local Demo Summary

## Result

Status: **passed**
Pack selection: `all`
Release count: **3**
Channel/support: `candidate/supported`
Registry URI: `file:///tmp/fogstack-parity-readiness/registry`

## Releases

| Bundle | Version | Pack | Validation record | Filesystem release pointer |
|---|---:|---|---|---|
| `fogstack.access` | `0.1.0` | `access` | `/tmp/fogstack-parity-readiness/validation/fogstack.access.validation.record.json` | `/tmp/fogstack-parity-readiness/registry/fogstack.access/0.1.0/release-pointer.json` |
| `fogstack.knowledge` | `0.1.0` | `knowledge` | `/tmp/fogstack-parity-readiness/validation/fogstack.knowledge.validation.record.json` | `/tmp/fogstack-parity-readiness/registry/fogstack.knowledge/0.1.0/release-pointer.json` |
| `fogstack.evaluation` | `0.1.0` | `evaluation` | `/tmp/fogstack-parity-readiness/validation/fogstack.evaluation.validation.record.json` | `/tmp/fogstack-parity-readiness/registry/fogstack.evaluation/0.1.0/release-pointer.json` |

## Key artifacts

- Publication gate: `/tmp/fogstack-parity-readiness/gate/fogstack.release-publication-gate.record.json`
- Registry root metadata: `/tmp/fogstack-parity-readiness/root/registry-root-metadata.json`
- Registry publication index: `/tmp/fogstack-parity-readiness/registry-publication/registry-publication.index.json`
- Revocation index: `/tmp/fogstack-parity-readiness/lifecycle/registry-revocation-index.json`
- Summary JSON: `/tmp/fogstack-parity-readiness/fogstack-local-demo.summary.json`
- Summary HTML: `/tmp/fogstack-parity-readiness/index.html`
- Artifact index: `/tmp/fogstack-parity-readiness/demo-artifacts.index.json`

## Checks

- `bundle_verified`
- `validation_record_emitted`
- `publication_set_built`
- `promotion_policy_passed`
- `approval_record_checked`
- `approval_signature_verified`
- `publication_gate_passed`
- `registry_index_built`
- `filesystem_registry_published`
- `filesystem_registry_checked`
- `revocation_index_checked`
- `registry_root_checked`

## Deploy readiness

| Artifact ID | Artifact | Ref | SHA-256 digest | Status |
|---|---|---|---|---|
| `deploy_node_profile` | Agent Machine node profile | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.agent-machine-node-profile.json` | `sha256:3d1398a898125927d9df6d0801a7abd17925eb92e1b536c0497c9bc50db4a69c` | `indexed` |
| `deploy_node_inventory_record` | Agent Machine node inventory | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.agent-machine-node-inventory.record.json` | `sha256:fad1e99aa983012ecbab9de09913ef4b5f4519d21f34eeb99698f5a4b93443c9` | `indexed` |
| `deploy_immutable_update_readiness_record` | Immutable update readiness | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.immutable-update-readiness.record.json` | `sha256:a29dfc7b5f8c6ac3383fedffe101ecf537466d80af0ffeff566948a50c433697` | `indexed` |
| `deploy_agent_corps_plan` | Agent Corps plan | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.runtime-contract.json` | `sha256:7207053688cb8723cc2e342fb73f627e3d719f6c2fe2ff2abad5d6e92a45105d` | `indexed` |
| `deploy_plan` | Deploy plan | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.deploy-plan.json` | `sha256:88f0e84218526f0f5318ea2030aea280f6797c67e86408890a5f8b509e2e5535` | `indexed` |
| `deploy_kubernetes_configmap` | Kubernetes ConfigMap | `/tmp/fogstack-parity-readiness/deploy/kubernetes/configmap.yaml` | `sha256:a66f7f0eae84f92bf3cd5622a8630c3c2c8f8fa240832fd2827d80e97a994463` | `indexed` |
| `deploy_kubernetes_deployment` | Kubernetes Deployment | `/tmp/fogstack-parity-readiness/deploy/kubernetes/deployment.yaml` | `sha256:c3001a679eb90e03a4b8e64c1f8e8c74b1654dca143e7380f1cc1fec31fe8d79` | `indexed` |
| `deploy_kubernetes_service` | Kubernetes Service | `/tmp/fogstack-parity-readiness/deploy/kubernetes/service.yaml` | `sha256:78142b1e95e5231fae7ccea6ec251bf368f520f456f9396790cc87674bfc9126` | `indexed` |
| `deploy_kubernetes_manifest_check_record` | Manifest check record | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.kubernetes-manifest-check.record.json` | `sha256:55f0bab7849121b0e4222b2f893c7daab37079f21e015dfccbdf3b18cb22c218` | `indexed` |
| `deploy_cluster_readiness_record` | Cluster readiness record | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.cluster-readiness.record.json` | `sha256:dba71c978ddd1625e018ccb819d7260e12266c23189da8e0311220e1b6f48bd4` | `indexed` |
| `deploy_gitops_bundle` | GitOps bundle | `/tmp/fogstack-parity-readiness/deploy/gitops/gitops-bundle.json` | `sha256:1f9442857778ed660c4e9a89985cec0b31abaabcaf4509b5208de018d1699fa9` | `indexed` |
| `deploy_gitops_application` | GitOps Application | `/tmp/fogstack-parity-readiness/deploy/gitops/application.yaml` | `sha256:2ef73dbf2c7d265130b3f4955e0e6f2b2599a847d9ae9cb768244780cd081986` | `indexed` |
| `deploy_gitops_kustomization` | GitOps Kustomization | `/tmp/fogstack-parity-readiness/deploy/gitops/kustomization.yaml` | `sha256:650d3d0b90774c2db8a1af486643a856ac616c871b7fd1d957490ae890ed7fd1` | `indexed` |
| `deploy_gitops_configmap` | GitOps ConfigMap | `/tmp/fogstack-parity-readiness/deploy/gitops/manifests/configmap.yaml` | `sha256:a66f7f0eae84f92bf3cd5622a8630c3c2c8f8fa240832fd2827d80e97a994463` | `indexed` |
| `deploy_gitops_deployment` | GitOps Deployment | `/tmp/fogstack-parity-readiness/deploy/gitops/manifests/deployment.yaml` | `sha256:c3001a679eb90e03a4b8e64c1f8e8c74b1654dca143e7380f1cc1fec31fe8d79` | `indexed` |
| `deploy_gitops_service` | GitOps Service | `/tmp/fogstack-parity-readiness/deploy/gitops/manifests/service.yaml` | `sha256:78142b1e95e5231fae7ccea6ec251bf368f520f456f9396790cc87674bfc9126` | `indexed` |
| `deploy_gitops_readiness_record` | GitOps readiness record | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.gitops-readiness.record.json` | `sha256:917a80994cd795df9f737956295471c3c54fe464554d22ff6a93b9949f74d5c2` | `indexed` |
| `deploy_live_cluster_preflight_record` | Live cluster preflight record | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.live-cluster-preflight.record.json` | `sha256:0c1e9192818e26623ab6bdb48c383c87d6b190b7af42277078f040f4a0aee688` | `indexed` |
| `deploy_runtime_adapter` | Runtime adapter | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.local-cluster-runtime-adapter.json` | `sha256:c0d88ccc33869d9a490d7b14f542e2fdadc182cd2f964321c0c575cd342e9705` | `indexed` |
| `deploy_runtime_dry_run_record` | Runtime dry-run record | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.runtime-dry-run.record.json` | `sha256:652fdf3d2b6cbd7c22fd035e6ea2def065a53e79216188f72de86b00f042d0a0` | `indexed` |
| `deploy_summary` | Deploy summary | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.deploy-demo.summary.json` | `sha256:1e86a4d8951ba7cf79babee4032402d5b2f349de04f612ce29e6579273dcc49a` | `indexed` |

## Live cluster preflight

- Status: `blocked`
- Mode: `read-only-live-preflight`
- Namespace: `fogstack-access`
- Mutated cluster: `False`
- Live apply allowed: `False`
- Human approval required: `True`
- Reason: `kubectl unavailable; live cluster preflight not attempted`

## GitOps readiness

| Artifact ID | Artifact | Ref | SHA-256 digest | Status |
|---|---|---|---|---|
| `deploy_gitops_readiness_record` | GitOps readiness record | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.gitops-readiness.record.json` | `sha256:917a80994cd795df9f737956295471c3c54fe464554d22ff6a93b9949f74d5c2` | `indexed` |

## Runtime evidence

| Artifact ID | Artifact | Ref | SHA-256 digest | Status |
|---|---|---|---|---|
| `deploy_runtime_adapter` | Runtime adapter | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.local-cluster-runtime-adapter.json` | `sha256:c0d88ccc33869d9a490d7b14f542e2fdadc182cd2f964321c0c575cd342e9705` | `indexed` |
| `deploy_runtime_dry_run_record` | Runtime dry-run record | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.runtime-dry-run.record.json` | `sha256:652fdf3d2b6cbd7c22fd035e6ea2def065a53e79216188f72de86b00f042d0a0` | `indexed` |

## Runtime readiness

| Signal | Value |
|---|---|
| AgentPlane run ID | `agentplane-run:fogstack.access:local-dry-run` |
| AgentPlane run ref | `agentplane://runs/fogstack.access/local-dry-run` |
| AgentPlane ref | `github://SocioProphet/agentplane` |
| Requested by | `human:operator` |
| AgentPlane execution mode | `dry-run` |
| AgentPlane approval state | `live-apply-requires-human-approval` |
| PolicyPlane decision ID | `policyplane-decision:fogstack.access:local-dry-run` |
| PolicyPlane decision ref | `policyplane://decisions/fogstack.access/local-dry-run` |
| PolicyPlane ref | `github://SocioProphet/policy-fabric` |
| PolicyPlane subject | `agentplane://runs/fogstack.access/local-dry-run` |
| PolicyPlane decision | `dry-run-allowed` |
| PolicyPlane effect | `allow-dry-run-deny-live-apply` |
| PolicyPlane reason | `Dry-run evidence is allowed; live apply remains denied until human approval.` |
| PolicyPlane live apply allowed | `false` |
| PolicyPlane human approval required | `true` |
| Node profile | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.agent-machine-node-profile.json` |
| Node profile digest | `sha256:3d1398a898125927d9df6d0801a7abd17925eb92e1b536c0497c9bc50db4a69c` |
| Dry-run mode | `dry-run` |
| Validation path | `contract-and-digest-only` |
| Mutated cluster | `false` |
| Live apply allowed | `false` |
| Human approval required | `true` |

| Use surface | Repo | Type | Governance |
|---|---|---|---|
| TurtleTerm | `github://SourceOS-Linux/TurtleTerm` | `terminal` | `first_class=true; agentplane_visible=true; policyplane_guarded=true` |
| BearBrowser | `github://SourceOS-Linux/BearBrowser` | `browser` | `first_class=true; agentplane_visible=true; policyplane_guarded=true` |

## Live apply planning

| Artifact ID | Artifact | Ref | SHA-256 digest | Status |
|---|---|---|---|---|
| `deploy_live_apply_plan_record` | Live apply plan record | `/tmp/fogstack-parity-readiness/deploy/fogstack.access.live-apply-plan.record.json` | `sha256:491103272aec26b8161ecfaf1a9d692cbe32b25b39d39e89925b6ccf64cd21e1` | `indexed` |

| Signal | Value |
|---|---|
| Mode | `plan-only` |
| Status | `blocked` |
| Live preflight status | `blocked` |
| Run performed | `false` |
| Mutated cluster | `false` |
| Live apply allowed | `false` |
| Future approval required | `true` |
