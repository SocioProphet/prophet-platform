# Pods We Ship (Bill of Materials: Prophet Platform + SocioProfit App)

This is the “what’s in the box” list.

## Third-party baseline (installed by our fabric)

- cert-manager
- external-secrets
- Istio: istio-base, istiod, ingress gateway
- kube-prometheus-stack (Prometheus/Grafana/Alertmanager)
- Loki (logs)
- Chaos Mesh (non-prod default)
- Argo CD (GitOps)

## Data plane

- Kafka (commit log / durability plane)
- MinIO (dev default; prod is external S3)
- Postgres via CloudNativePG operator (HA within region)
- Redis (replication)
- Memcached
- Blazegraph

## Time-series/analytics

- QuestDB (hot)
- ClickHouse operator + ClickHouseInstallation (cold/heavy)
- ArcticDB gateway (dataset/version artifacts)

## Prophet Platform (1st-party pods)

- prophet-control-plane (API)
- prophet-ingest-gateway
- prophet-lake-writer
- prophet-materializer-questdb
- prophet-materializer-clickhouse
- prophet-query-gateway
- prophet-reasoner
- prophet-agent (DaemonSet)

> NOTE: Global HA/DR also requires a platform-level durability plane (commit log + immutable lake replication).
> This repo standardizes the k8s runtime; the HA/DR durability plane is documented separately.


## SocioProfit App (1st-party app pods)

- socioprofit-api
- socioprofit-web
- socioprofit-worker


## Ray ML (Train + Serve)

- kuberay-operator
- prophet-ray-serve (RayService)
- prophet-ray-train (RayJob)


## MLOps ecosystem add-ons (optional)

- argo-workflows
- mlflow
- feast-operator
- spark-operator
- opentelemetry-operator
- kserve (kserve-crds + kserve controller)
- seldon-core-v2 (crds + operator)
- gpu-operator


## Time-series suite (reference images + workflows)

Prophet ships a reference time-series suite as:
- training images (classical, GARCH, deep, surfaces)
- Argo workflow templates (train→eval→deploy)

See:
- `docs/time-series-suite-v1.md`
- `docs/time-series-eval-gates.md`
- `docs/time-series-model-families.md`
- `docker/` and `workflows/`

- prophet-ts-workflows (Argo templates + example specs)
