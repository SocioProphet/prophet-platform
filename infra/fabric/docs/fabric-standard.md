# Socioprofit Kubernetes Fabric Standard

We interpret “multi-mesh fabric” as:

- **Multi-cluster**: many Kubernetes clusters (regions, edges, compliance domains)
- **One operational standard**: same baseline addons, same policies, same observability
- **A service mesh** providing mTLS + traffic policy + telemetry between services

This repo is an *opinionated* baseline you can fork and evolve.

## Baseline add-ons (every cluster)

1. cert-manager (cert issuance)
2. external-secrets (pull secrets from your chosen secret backend)
3. Istio (service mesh)
4. Observability (Prometheus stack + logs)
5. Chaos Mesh (non-prod): verify HA/DR claims with real failures

## Data plane add-ons (core clusters)

- Commit log: Kafka (dev) / production log service
- Postgres: CloudNativePG operator + a cluster CR (HA within region)
- Redis: cache + queue-ish use cases (not source of truth)
- Memcached: ephemeral cache
- Blazegraph: RDF/SPARQL store (stateful)
- Time-series/analytics: QuestDB + ClickHouse + ArcticDB gateway (optional)

## Golden rules

- **Source-of-truth durability is platform-owned** (log + immutable lake).
  Engines are materialized views and query accelerators.
- **Do not assume DB-native HA is enough**.
  HA/DR is a product feature that must be testable and repeatable.
- **Mesh the apps by default**.
  For stateful databases, be conservative with sidecars: start with *no injection*,
  then enable where it’s proven safe for your workload.

## Multi-region

Deploy the same helmfile to every region cluster, but with region-specific values overlays:
- storage class names
- node pools
- object storage endpoints and replication policies
- external DNS / gateways

See `docs/multi-region.md`.
