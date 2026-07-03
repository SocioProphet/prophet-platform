# Multi-region / Multi-cluster notes

A pragmatic pattern:

- Each region is its own Kubernetes cluster.
- Each cluster runs the same baseline add-ons via GitOps (Argo CD).
- Cross-region DR is done by replicating:
  - commit log (or its checkpoints)
  - immutable lake/object storage
  - control-plane state (Postgres logical replication or backup/restore)

## Istio multi-cluster

Istio supports multi-cluster patterns using gateways and shared trust.
Start with sidecar mode for stability, then evaluate ambient mode for lower overhead.

Official Helm repo:
- helm repo add istio https://istio-release.storage.googleapis.com/charts

See Istio docs for multi-cluster topologies and the “east-west gateway” pattern.
