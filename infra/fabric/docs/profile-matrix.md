# Profile matrix (Edge vs Core vs DR)

We deploy the same “fabric,” but different **profiles** choose different atoms.

| Atom | Edge-Min | Edge-Full | Core | DR |
|---|---:|---:|---:|---:|
| cert-manager | ✅ | ✅ | ✅ | ✅ |
| external-secrets | ✅ | ✅ | ✅ | ✅ |
| Istio (mesh) | ✅ | ✅ | ✅ | ✅ |
| observability | ✅ (agent/light) | ✅ | ✅ | ✅ |
| Argo CD | ✅ | ✅ | ✅ | ✅ |
| Chaos Mesh | ❌ | ❌ | ✅ (non-prod) | ✅ (non-prod) |
| Postgres (CNPG) | ❌ | ✅ | ✅ | ✅ |
| Redis | ✅ | ✅ | ✅ | ✅ |
| Memcached | ✅ | ✅ | ✅ | ✅ |
| Blazegraph | ❌ | ✅ | ✅ | ✅ |
| QuestDB | ✅ | ✅ | ✅ | ✅ |
| ClickHouse | ❌ | ❌/✅ | ✅ | ✅ |
| ArcticDB gateway | ❌ | ✅ | ✅ | ✅ |
| prophet-control-plane | ❌ | ❌ | ✅ | ✅ |
| prophet-ingest-gateway | ✅ | ✅ | ✅ | ✅ |
| prophet-lake-writer | ❌ | ❌ | ✅ | ✅ |
| sp-materializers | ✅ (QuestDB) | ✅ | ✅ | ✅ |
| prophet-query-gateway | ✅ | ✅ | ✅ | ✅ |
| prophet-reasoner | ✅ (small) | ✅ | ✅ (big) | ✅ |

Interpretation:
- **Edge-Min**: hot ingest + local queries + cache; pushes upstream.
- **Core**: full platform, analytics, control plane.
- **DR**: like Core but in standby mode (or partition-active).


### Ray ML plane (recommended)

| Atom | Edge-Min | Edge-Full | Core | DR |
|---|---:|---:|---:|---:|
| kuberay-operator | ✅ | ✅ | ✅ | ✅ |
| prophet-ray-serve | ✅ (small) | ✅ | ✅ (big) | ✅ |
| prophet-ray-train | ❌ | ❌ | ✅ (GPU) | ✅ (standby) |

Notes:
- Train is core-only by default.
- Serve can exist at edge for low-latency inference.


### MLOps ecosystem (optional)

| Atom | Edge-Min | Edge-Full | Core | DR |
|---|---:|---:|---:|---:|
| argo-workflows | ❌ | ❌ | ✅ | ✅ |
| mlflow | ❌ | ❌ | ✅ | ✅ |
| feast-operator | ❌ | ❌ | ✅ | ✅ |
| spark-operator | ❌ | ❌ | ✅ | ✅ |
| opentelemetry-operator | ✅ (light) | ✅ | ✅ | ✅ |
| kserve | ❌ | ✅ (if needed) | ✅ (if chosen) | ✅ |
| seldon-core-v2 | ❌ | ❌ | ✅ (if chosen) | ✅ |
| gpu-operator | ❌ | ❌ | ✅ (GPU pools) | ✅ (GPU pools) |

Notes:
- “Core” is where training and registry live.
- Edge is generally inference-only, unless you have a specific edge training requirement.


### Time-series suite orchestration

| Atom | Edge-Min | Edge-Full | Core | DR |
|---|---:|---:|---:|---:|
| prophet-ts-workflows | ❌ | ❌ | ✅ | ✅ |

Notes:
- These workflow templates live in core/DR because they orchestrate training and promotions.
