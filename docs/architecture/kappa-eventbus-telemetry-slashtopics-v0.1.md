# Kappa Event Bus + Telemetry over Slash Topics — Design & Build Manifest v0.1

**Status:** authored 2026-07-31 · supersedes the direct-capture approach in
`observability-capture-liveness-strategy-v0.1.md` (that path is retired as the
design; kept only as an optional labeled stopgap).
**Owner:** Platform / DevSecOps
**Conforms to:** ADR-030 Map-Log · standard-100 CDM/EventEnvelope · standard-138
Evidence Receipt Spine · slash-topics (`TopicPackRef`, `MembraneDecision`,
trust store) · `INTEGRATION-MAP` kappa-core-over-Hypercore.

## 1. Principle
*Contracts are the product; engines are implementations.* Telemetry and ops
signals are **`EventEnvelope` CDM events on an append-only Map Log**, whose
**topic identity is a signed Slash Topic Pack** (`TopicPackRef`), whose
**produce/consume is gated by the capability membrane** (`MembraneDecision`,
receipted to the spine). The **transport is swappable**: Kafka (KRaft) in dev →
kappa-core-over-Hypercore in prod — with **zero producer/consumer change**.

## 2. Data path
```
producer (OTel collector / app / agent)
  └─ emits EventEnvelope{ id,type,source,subject,time,payload }
       scoped to slash topic  /telemetry/logs | /metrics | /traces | /ops/alerts
        └─ New Hope resolves slash topic -> policy_context
            └─ Capability Membrane -> MembraneDecision (allow/deny + receipt -> spine)
                └─ APPEND to Map Log stream (engine: Kafka KRaft dev / Hypercore prod)
                     └─ projections (consumers) rebuild views:
                          Loki (logs) · Tempo (traces) · Prometheus (metrics) ·
                          DevSecOps Intelligence Workroom (LogQL/PromQL/subscribe)
```
Topic name is the transport binding of the pack (`pack_digest`-derived);
`locality_class` drives storage tiering, `ttl_s` drives retention.

## 3. Reuse (already in prophet-platform — do NOT reinvent)
- `contracts/TopicPackRef.v0.1.json`, `contracts/MembraneDecision.v0.1.json`,
  `trust/slash_topic_trust_store.json`
- `infra/fabric/helm/values/kafka.yaml` (KRaft commit log, dev), `sovereign-broker`
  (`workspace-broker:dev`)
- observability stack (Loki/Tempo/Prometheus) — **re-cast as projection consumers**
- EventEnvelope from `SourceOS-Linux/sourceos-spec` (pin in `standards.lock.yaml`)

## 4. BUILD MANIFEST (nothing forgotten — tracked checklist)

### 4.1 IaC (tofu, `infra/tofu/`)
- [ ] `modules/eventlog-storage`: GCS buckets per `locality_class`
  (`shared-near`/`remote-cold`/`offline-archival`) for Map-Log tiering + topic-pack
  cold store; lifecycle rules keyed to `ttl_s`; CMEK.
- [ ] Secret Manager: broker SASL creds, Map-Log signing key, slash-topic trust
  anchors — seeded via ExternalSecret (never in repo).
- [ ] Workload-Identity SAs: producer, projection-consumers, topic-registry (least-priv).
- [ ] Cloud Monitoring alert policy: Map-Log ingestion == 0 (mirrors in-cluster rule).

### 4.2 Container artifacts (Dockerfiles + sovereign CI build, digest+SBOM per profile)
- [ ] `telemetry-producer`: OTel receiver → EventEnvelope encoder → membrane-gated
  append to Map Log.
- [ ] `mlog-projection-loki`, `mlog-projection-tempo`: consume Map Log → write the
  Loki/Tempo projection (idempotent, offset-tracked, replayable).
- [ ] `slashtopic-registry`: resolves slash topic ↔ `TopicPackRef`, verifies pack
  signature against the trust store, exposes New Hope `policy_context`.
- [ ] `membrane-gate`: produce/consume admission → `MembraneDecision` + receipt to spine.
- [ ] No `:latest`; image pinned + digest recorded on promote.

### 4.3 k8s (`infra/k8s/eventbus/` + `infra/k8s/observability/`)
- [ ] Kafka KRaft StatefulSet + Service + PVC (dev commit log; Hypercore swap later).
- [ ] `sovereign-broker`/`workspace-broker` wiring to the commit log.
- [ ] Deployments: telemetry-producer, mlog-projection-loki, mlog-projection-tempo,
  slashtopic-registry, membrane-gate.
- [ ] Services + NetworkPolicies (producer←cluster, consumers←broker only).
- [ ] ServiceMonitors: broker, producer, consumers, registry (so liveness has data).
- [ ] Loki/Tempo re-pointed to receive **only** from mlog-projection consumers.

### 4.4 Lifecycles
- [ ] Topic-pack lifecycle: register → sign → publish `TopicPackRef` → rotate;
  pin as upstream in `standards.lock.yaml`.
- [ ] Map-Log retention/compaction + tiering hot→cold→archival by `locality_class`/`ttl_s`.
- [ ] Consumer offsets / replay / rebuild-projection-from-zero runbook.
- [ ] MembraneDecision receipts streamed to the Evidence Receipt Spine.
- [ ] **Liveness reframed**: canary emits an EventEnvelope on `/telemetry/logs`;
  alert if the Map Log receives 0 events per topic (guaranteed input ⇒ silence=failure).
- [ ] **Producer-before-storage CI gate** extended: every slash topic MUST have a
  producer AND a projection consumer, or CI fails (waiver = signed exception).

## 5. Disposition of PR #1161
Held. Loki/Tempo become **projection consumers**, not push targets; the direct
promtail→Loki and Alertmanager→PagerDuty paths are retired from the design.
Alerts are events on `/ops/alerts`; PagerDuty is a consumer/sink of that topic.

## 6. Rollout order
1. Pin EventEnvelope + slash-topics in `standards.lock.yaml`; publish the four
   Topic Packs (`/telemetry/{logs,metrics,traces}`, `/ops/alerts`).
2. Stand up the commit log (Kafka KRaft dev) + broker + slashtopic-registry + membrane-gate.
3. telemetry-producer → append EventEnvelope; then mlog-projection-loki/tempo.
4. Re-point Loki/Tempo as consumers; wire the DevSecOps workroom to subscribe.
5. Liveness-on-the-log + producer-before-storage gate.
6. IaC tiering (GCS by locality_class) + Hypercore/kappa-core engine swap (prod).
```
```
## 7. Meshed intelligence feedback loop (SynapseIQ · Holmes · Sherlock · GDI)

The intelligence tier is what makes the Map Log a *feedback* loop, not a data
grave. All four are **both producers and consumers** of slash topics — they
reason over the same append-only log and emit derived `EventEnvelope` events
back onto it, gated by the membrane like any other producer.

```
telemetry/ops events on the Map Log (/telemetry/*, /ops/alerts)
  → SynapseIQ (enrichment/collector/reasoning): normalize + KKO/Peircean
      classify → emit /intel/enriched
  → Sherlock-Search (Tantivy+Qdrant): index enriched events → retrieval;
      emit /intel/retrieval
  → Holmes (:8091 /verify): evidence-grounded deduction over Sherlock
      retrieval → emit /intel/verdicts
  → global-devsecops-intelligence (AI4IT ops profile): correlate verdicts +
      telemetry → emit /ops/findings + /ops/actions
  → actions re-enter as ops events → telemetry → re-analysis  ⟲ (closed loop)
```
Existing wiring reused: Sherlock is already Holmes' retrieval component and the
`corpus` source in search-gateway; Qdrant (`mesh-qdrant`) is the shared vector
substrate; SynapseIQ plane (reasoning/enrichment/tabular/control-plane/collector)
and Holmes are already deployed. GDI already has k8s base + ArgoCD wiring but
**no image build** — it is a draft profile that must become a running consumer.

### 7.1 Build additions (tracked)
- [ ] **Mesh adapters** — a thin producer/consumer binding per component
  (SynapseIQ, Sherlock, Holmes, GDI) that subscribes to its input slash topics
  and publishes `EventEnvelope` outputs, membrane-gated. Prefer a shared
  `mesh-sdk` over four bespoke clients.
- [ ] **Slash Topic Packs** for the intel plane: `/intel/enriched`,
  `/intel/retrieval`, `/intel/verdicts`, `/ops/findings`, `/ops/actions`
  (signed, `policy_bundle_id`, `locality_class`, `ttl_s`).
- [ ] **Roll GDI as a service**: Dockerfile (Python) + `images.yml` matrix entry
  + CI build (SBOM+digest) + `deploy/values/global-devsecops-intelligence.yaml`;
  promote real sha into the existing k8s base (currently placeholder image).
- [ ] **GDI prophet-platform IaC**: Workload-Identity SA (least-priv: consume
  `/telemetry/*` + `/intel/verdicts`, produce `/ops/*`), Secret Manager refs,
  GCS profile/model store per `locality_class`, ServiceMonitor.
- [ ] **Feedback-loop liveness**: canary claim traverses the full loop
  (enriched→retrieval→verdict→finding→action); alert if any hop's slash topic
  goes silent (never-fired=suspect, end-to-end across the mesh).
- [ ] **Producer-before-storage gate** extended to the intel topics: every
  `/intel/*` and `/ops/*` topic MUST have a producer AND a consumer.

## 8. Ownership / lanes
Intelligence services stay in their repos (`synapseiq`, `holmes`,
`sherlock-search`, `SocioProphet/global-devsecops-intelligence`); prophet-platform
owns only the **mesh substrate, IaC, deploy wiring, and slash-topic packs**. The
authoritative logic lives upstream and is pinned (`standards.lock.yaml`).

---
**Gated:** every apply/deploy/image-push is a gated action (operator runs it).
This doc is the contract; concrete artifacts are built against §4 and §7 and
tracked there.
