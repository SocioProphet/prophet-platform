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
**Gated:** every apply/deploy/image-push is a gated action (operator runs it).
This doc is the contract; concrete artifacts are built against §4 and tracked there.
